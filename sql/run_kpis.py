"""Ejecuta sql/kpis.sql y deja el informe en docs/resultados_kpis.md.

Parte el fichero por las líneas ``-- KPI:``. Cada bloque es una consulta
que se lee con ``pandas.read_sql_query`` sobre la conexión sqlite3: no
hace falta SQLAlchemy ni tabulate. La tabla Markdown la pinta una función
propia, con un tope de 20 filas y los reales a 2 decimales.

La base por defecto es data/retail_stock.db, resuelta desde este archivo
y no desde el directorio de trabajo.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DIR_SQL = Path(__file__).resolve().parent
RUTA_KPIS = DIR_SQL / "kpis.sql"
RUTA_DB_DEFECTO = RAIZ_PROYECTO / "data" / "retail_stock.db"
RUTA_INFORME_DEFECTO = RAIZ_PROYECTO / "docs" / "resultados_kpis.md"

MARCA_KPI = "-- KPI:"
MAX_FILAS = 20
SEPARADOR_DECIMAL = "."


def configurar_salida() -> None:
    """Evita UnicodeEncodeError si la consola de Windows no es UTF-8."""
    for flujo in (sys.stdout, sys.stderr):
        reconfigure = getattr(flujo, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


def resolver_desde_raiz(valor: str | None, defecto: Path) -> Path:
    """Una ruta relativa se cuelga de la raíz del proyecto; una absoluta, no."""
    if valor is None:
        return defecto
    ruta = Path(valor)
    if not ruta.is_absolute():
        ruta = RAIZ_PROYECTO / ruta
    return ruta


def partir_kpis(texto: str) -> list[tuple[str, str]]:
    """Corta el SQL por las líneas que empiezan por ``-- KPI:``.

    El texto anterior al primer marcador es cabecera y no se ejecuta.
    El título es lo que queda en esa línea después del marcador.
    """
    bloques: list[tuple[str, str]] = []
    titulo: str | None = None
    lineas: list[str] = []
    for linea in texto.splitlines():
        if linea.startswith(MARCA_KPI):
            if titulo is not None:
                bloques.append((titulo, "\n".join(lineas).strip()))
            titulo = linea[len(MARCA_KPI) :].strip()
            lineas = []
            continue
        if titulo is not None:
            lineas.append(linea)
    if titulo is not None:
        bloques.append((titulo, "\n".join(lineas).strip()))
    if not bloques:
        raise ValueError(f"No hay líneas '{MARCA_KPI}' en {RUTA_KPIS}.")
    return bloques


def comentarios_de(sql: str) -> list[str]:
    """Devuelve las líneas de comentario del bloque, sin el ``-- ``."""
    notas: list[str] = []
    for linea in sql.splitlines():
        desnuda = linea.strip()
        if not desnuda.startswith("--"):
            continue
        notas.append(desnuda[2:].strip())
    return notas


def formatear_valor(valor: object, *, reales: bool) -> str:
    """Presenta un valor de celda.

    Los reales van con 2 decimales (redondeo de presentación, no de cálculo).
    Los enteros se quedan sin decimales: un mes o un puesto no es un importe.
    El tipo lo decide la columna, no la fila: ``iterrows`` promociona un
    entero a float si al lado hay un importe, y entonces 577523 saldría
    como 577523.00. Nulo se escribe ``n/d`` para que enero, que no tiene
    mes anterior, no parezca una variación de cero.
    """
    if valor is None:
        return "n/d"
    try:
        if pd.isna(valor):
            return "n/d"
    except TypeError:
        pass
    if reales:
        return f"{float(valor):.2f}"
    if isinstance(valor, str):
        return valor.replace("|", "\\|").replace("\n", " ")
    if isinstance(valor, (bool, np.bool_)):
        return "1" if valor else "0"
    if isinstance(valor, (int, np.integer)):
        return str(int(valor))
    if isinstance(valor, (float, np.floating)):
        if float(valor).is_integer():
            return str(int(valor))
        return f"{float(valor):.2f}"
    return str(valor).replace("|", "\\|").replace("\n", " ")


def tabla_markdown(df: pd.DataFrame, max_filas: int = MAX_FILAS) -> str:
    """Tabla Markdown sin tabulate. A lo sumo ``max_filas`` filas de datos.

    Las columnas numéricas se alinean a la derecha (``---:``) para que el
    importe no se lea como texto. Si la consulta trae más filas, se avisa:
    el tope es de presentación, la consulta no se recorta en SQL.
    """
    if df.empty:
        return "_Sin filas._"

    mostradas = df.head(max_filas)
    columnas = [str(columna) for columna in mostradas.columns]
    es_real = [
        pd.api.types.is_float_dtype(mostradas[columna]) for columna in mostradas.columns
    ]
    numerica = [
        pd.api.types.is_numeric_dtype(mostradas[columna]) for columna in mostradas.columns
    ]

    cabecera = "| " + " | ".join(columnas) + " |"
    separadores = ["---:" if es_numerica else "---" for es_numerica in numerica]
    separador = "| " + " | ".join(separadores) + " |"
    # Por columna, no por fila: así un entero no hereda el dtype float del importe.
    por_columna = [
        [formatear_valor(valor, reales=es_real[j]) for valor in mostradas.iloc[:, j].tolist()]
        for j in range(mostradas.shape[1])
    ]
    filas = [
        "| " + " | ".join(por_columna[j][i] for j in range(len(columnas))) + " |"
        for i in range(len(mostradas))
    ]

    texto = "\n".join([cabecera, separador, *filas])
    ocultas = len(df) - len(mostradas)
    if ocultas > 0:
        texto += (
            f"\n\n_{ocultas} filas más no mostradas "
            f"(límite de presentación: {max_filas})._"
        )
    return texto


def fecha_de_corte(conn: sqlite3.Connection) -> str:
    """La misma regla que las consultas: MAX(fecha) de fact_stock."""
    fila = conn.execute("SELECT MAX(fecha) FROM fact_stock").fetchone()
    if fila is None or fila[0] is None:
        raise RuntimeError("fact_stock está vacía: no hay fecha de corte.")
    return str(fila[0])


def ejecutar(conn: sqlite3.Connection, titulo: str, sql: str) -> pd.DataFrame:
    """Lanza un bloque. El mensaje nombra el KPI si la consulta revienta."""
    if "SELECT" not in sql.upper():
        raise ValueError(f"El KPI '{titulo}' no tiene SELECT.")
    try:
        return pd.read_sql_query(sql, conn)
    except Exception as exc:
        raise RuntimeError(f"Fallo en el KPI '{titulo}': {exc}") from exc


def construir_informe(
    resultados: list[tuple[str, str, pd.DataFrame]],
    fecha_corte: str,
    generado: str,
) -> str:
    """Markdown con título, nota de datos sintéticos y una tabla por KPI."""
    lineas = [
        "# KPIs de stock y ventas — SportStock",
        "",
        "Datos 100% sintéticos de la cadena ficticia SportStock. "
        "No describen a ninguna enseña real.",
        "",
        f"Fecha de generación: {generado}.",
        "",
        f"Fecha de corte: {fecha_corte} (`MAX(fecha)` de `fact_stock`). "
        "Las consultas de cobertura y de estado usan esa fecha; el resto, el año completo.",
        "",
        "Los reales se muestran con 2 decimales. Es redondeo de presentación: "
        "el cálculo se hace en SQL sin redondear. Un nulo (enero, o cobertura "
        "sin venta en 28 días) se escribe `n/d`, no cero.",
        "",
    ]
    for titulo, sql, df in resultados:
        lineas.append(f"## {titulo}")
        lineas.append("")
        notas = comentarios_de(sql)
        if notas:
            lineas.extend(f"> {nota}" for nota in notas)
            lineas.append("")
        lineas.append(tabla_markdown(df))
        lineas.append("")
    return "\n".join(lineas).rstrip() + "\n"


def resumen_consola(titulo: str, df: pd.DataFrame) -> str:
    """Una línea por KPI: filas y, si es el resumen global, las cifras de cabecera."""
    extra = ""
    if len(df) == 1 and {"importe", "margen_pct"}.issubset(df.columns):
        importe = float(df.iloc[0]["importe"])
        margen = float(df.iloc[0]["margen_pct"])
        extra = f" | importe {importe:.2f} | margen {margen:.2f}%"
    if len(df) > MAX_FILAS:
        extra += f" | se muestran {MAX_FILAS}"
    etiqueta = "fila" if len(df) == 1 else "filas"
    return f"  {titulo}: {len(df)} {etiqueta}{extra}"


def main() -> None:
    configurar_salida()
    parser = argparse.ArgumentParser(
        description="Ejecuta los KPI de SportStock y escribe el informe Markdown."
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Base SQLite. Por defecto data/retail_stock.db, desde la raíz del proyecto.",
    )
    parser.add_argument(
        "--salida",
        default=None,
        help="Informe Markdown. Por defecto docs/resultados_kpis.md.",
    )
    args = parser.parse_args()
    ruta_db = resolver_desde_raiz(args.db, RUTA_DB_DEFECTO)
    ruta_informe = resolver_desde_raiz(args.salida, RUTA_INFORME_DEFECTO)

    if not ruta_db.is_file():
        raise FileNotFoundError(
            f"No está la base {ruta_db}. Generarla con sql/load.py."
        )
    if not RUTA_KPIS.is_file():
        raise FileNotFoundError(f"No está {RUTA_KPIS}.")

    version = sqlite3.sqlite_version_info
    if version < (3, 25, 0):
        raise RuntimeError(
            f"SQLite {sqlite3.sqlite_version} no tiene funciones de ventana (hace falta >= 3.25)."
        )

    bloques = partir_kpis(RUTA_KPIS.read_text(encoding="utf-8"))
    conn = sqlite3.connect(ruta_db)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        corte = fecha_de_corte(conn)
        resultados = [
            (titulo, sql, ejecutar(conn, titulo, sql)) for titulo, sql in bloques
        ]
    finally:
        conn.close()

    generado = datetime.now().strftime("%Y-%m-%d %H:%M")
    informe = construir_informe(resultados, corte, generado)
    ruta_informe.parent.mkdir(parents=True, exist_ok=True)
    ruta_informe.write_text(informe, encoding="utf-8")

    print(f"Informe escrito en {ruta_informe}", flush=True)
    print(f"Fecha de corte: {corte}", flush=True)
    for titulo, _sql, df in resultados:
        print(resumen_consola(titulo, df), flush=True)


if __name__ == "__main__":
    main()
