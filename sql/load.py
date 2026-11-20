"""Carga los CSV de data/raw en SQLite con el modelo en estrella.

Borra la base, ejecuta schema.sql y vuelca las seis tablas con
``DataFrame.to_sql`` sobre las tablas ya creadas (no deja que pandas las
invente). El orden es dimensiones y después hechos: las claves foráneas
están activas y no se aplazan.

La conexión es sqlite3 de la librería estándar. No se usa SQLAlchemy:
``to_sql`` acepta un ``sqlite3.Connection`` y el proyecto no depende de
ese paquete.

pandas confirma la transacción al terminar cada ``to_sql``. El contrato
pide una sola transacción, así que ``ConexionCarga`` aplaza ese commit
hasta que dimensiones y hechos han entrado y ``PRAGMA foreign_key_check``
no ha devuelto filas.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

# Raíz calculada desde este archivo (sql/load.py), no desde el cwd.
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DIR_SQL = Path(__file__).resolve().parent
DIR_RAW = RAIZ_PROYECTO / "data" / "raw"
RUTA_SCHEMA = DIR_SQL / "schema.sql"
RUTA_DB_DEFECTO = RAIZ_PROYECTO / "data" / "retail_stock.db"

# Dimensiones primero. fact_ventas y fact_stock referencian a las cuatro.
ORDEN_CARGA: tuple[tuple[str, str], ...] = (
    ("categorias.csv", "dim_categoria"),
    ("productos.csv", "dim_producto"),
    ("tiendas.csv", "dim_tienda"),
    ("calendario.csv", "dim_calendario"),
    ("ventas.csv", "fact_ventas"),
    ("stock_diario.csv", "fact_stock"),
)

COLUMNAS_BOOLEANAS = ("es_fin_de_semana", "es_rebajas", "es_black_friday")
MAPA_BOOLEANO = {"true": 1, "false": 0, "1": 1, "0": 0}

CHUNK_FILAS = 50_000


class ConexionCarga(sqlite3.Connection):
    """Conexión cuyo ``commit`` se puede aplazar durante la carga.

    ``isinstance(conn, sqlite3.Connection)`` sigue siendo cierto, que es
    lo que pandas exige para usar el camino sqlite3 y no SQLAlchemy.
    """

    aplazar_commit = False

    def commit(self) -> None:
        if self.aplazar_commit:
            return
        super().commit()


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


def resolver_ruta_bd(valor: str | None) -> Path:
    """Resuelve ``--db`` desde la raíz del proyecto, no desde el cwd.

    Una ruta absoluta se respeta. Una relativa se cuelga de la raíz
    calculada con ``__file__``, igual que el valor por defecto
    ``data/retail_stock.db``.
    """
    if valor is None:
        return RUTA_DB_DEFECTO
    ruta = Path(valor)
    if not ruta.is_absolute():
        ruta = RAIZ_PROYECTO / ruta
    return ruta


def borrar_bd(ruta: Path) -> None:
    """Quita la base y los ficheros de journal por si quedó un WAL a medias."""
    for candidato in (ruta, Path(str(ruta) + "-wal"), Path(str(ruta) + "-shm")):
        if candidato.exists():
            candidato.unlink()


def leer_csv(ruta: Path) -> pd.DataFrame:
    """Lee un CSV y deja los booleanos en 0/1, que es lo que espera el CHECK.

    pandas interpreta True/False del calendario como ``bool``. SQLite no
    tiene tipo booleano y el esquema declara INTEGER con ``IN (0, 1)``.
    """
    df = pd.read_csv(ruta, encoding="utf-8")
    for columna in COLUMNAS_BOOLEANAS:
        if columna not in df.columns:
            continue
        serie = df[columna]
        if pd.api.types.is_bool_dtype(serie):
            df[columna] = serie.astype("int64")
            continue
        mapeado = serie.astype(str).str.strip().str.lower().map(MAPA_BOOLEANO)
        if mapeado.isna().any():
            raise ValueError(f"{ruta.name}: valores no booleanos en {columna}.")
        df[columna] = mapeado.astype("int64")
    return df


def aplicar_pragmas(conn: sqlite3.Connection) -> None:
    """Activa las FK y afloja el journal solo durante la carga.

    ``journal_mode = MEMORY`` no se persiste en el fichero: la siguiente
    conexión (run_kpis.py) abre la base en el modo normal. ``synchronous
    = OFF`` acelera el volcado; el commit final deja el fichero escrito.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = MEMORY")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -131072")
    activas = conn.execute("PRAGMA foreign_keys").fetchone()
    if activas is None or activas[0] != 1:
        raise RuntimeError("SQLite no ha activado PRAGMA foreign_keys.")


def crear_esquema(conn: sqlite3.Connection) -> None:
    """Ejecuta schema.sql. ``executescript`` confirma antes de lanzarlo."""
    if not RUTA_SCHEMA.is_file():
        raise FileNotFoundError(f"No está el esquema: {RUTA_SCHEMA}")
    conn.executescript(RUTA_SCHEMA.read_text(encoding="utf-8"))
    conn.execute("PRAGMA foreign_keys = ON")


def cargar_tablas(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    """Inserta cada CSV con to_sql(append) y devuelve el conteo real.

    El conteo sale de ``SELECT COUNT(*)``, no de ``len(df)``: así se ve
    que la fila llegó a la tabla y no solo al DataFrame.
    """
    cargadas: list[tuple[str, int]] = []
    for csv_nombre, tabla in ORDEN_CARGA:
        ruta = DIR_RAW / csv_nombre
        if not ruta.is_file():
            raise FileNotFoundError(f"Falta el CSV: {ruta}")
        inicio = time.perf_counter()
        df = leer_csv(ruta)
        try:
            df.to_sql(
                tabla,
                conn,
                if_exists="append",
                index=False,
                chunksize=CHUNK_FILAS,
            )
        except Exception as exc:
            raise RuntimeError(f"Fallo al cargar {tabla} desde {csv_nombre}: {exc}") from exc
        filas = conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()
        n = int(filas[0]) if filas is not None else 0
        if n != len(df):
            raise RuntimeError(
                f"{tabla}: el CSV tiene {len(df)} filas y la tabla {n}."
            )
        segundos = time.perf_counter() - inicio
        print(f"  {tabla}: {n} filas ({segundos:.1f} s)", flush=True)
        cargadas.append((tabla, n))
    return cargadas


def comprobar_claves(conn: sqlite3.Connection) -> None:
    """``foreign_key_check`` devuelve una fila por violación. Vacío = bien."""
    violaciones = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violaciones:
        muestra = "; ".join(str(fila) for fila in violaciones[:5])
        raise RuntimeError(
            f"PRAGMA foreign_key_check: {len(violaciones)} violaciones. {muestra}"
        )


def cargar(ruta_db: Path) -> None:
    """Borra, recrea y carga. Si algo falla, la transacción no se confirma."""
    ruta_db.parent.mkdir(parents=True, exist_ok=True)
    borrar_bd(ruta_db)
    conn = sqlite3.connect(ruta_db, factory=ConexionCarga)
    try:
        aplicar_pragmas(conn)
        crear_esquema(conn)
        print(f"Esquema creado en {ruta_db}", flush=True)
        conn.aplazar_commit = True
        cargar_tablas(conn)
        comprobar_claves(conn)
        if not conn.in_transaction:
            raise RuntimeError(
                "La carga no quedó en una sola transacción: "
                "pandas confirmó antes del foreign_key_check."
            )
        conn.aplazar_commit = False
        conn.commit()
        print("PRAGMA foreign_key_check: 0 violaciones", flush=True)
    except Exception:
        conn.aplazar_commit = False
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    configurar_salida()
    parser = argparse.ArgumentParser(
        description="Carga los CSV sintéticos de SportStock en una base SQLite."
    )
    parser.add_argument(
        "--db",
        default=None,
        help=(
            "Ruta de la base. Por defecto data/retail_stock.db, resuelta "
            "desde la raíz del proyecto (directorio de sql/load.py), no desde el cwd."
        ),
    )
    args = parser.parse_args()
    cargar(resolver_ruta_bd(args.db))


if __name__ == "__main__":
    main()
