"""Replica las medidas DAX de _Medidas en pandas y deja el contraste por escrito.

Lee los CSV de data/raw (no la base SQLite) y escribe docs/validacion_medidas.md.
La columna de Power BI se deja en pendiente: se rellena al abrir el .pbip.

Dos contextos, los dos sobre el año completo del calendario:
- A: todas las tiendas y productos. Último día = 2025-12-31.
- B: tienda 1 y categoría Running.
Ventas Mes Anterior y Var % vs Mes Anterior no se evalúan sobre el año movido
un mes: el mes actual de ese contraste es diciembre y el anterior noviembre.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Raíz desde este archivo, no desde el directorio de trabajo.
RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ / "data" / "raw"
SALIDA = RAIZ / "docs" / "validacion_medidas.md"

# Orden y texto de la tabla. La fórmula es la traducción breve del DAX, no el código.
MEDIDAS = (
    ("Ventas Importe", "SUM(importe)", 2, False),
    ("Unidades Vendidas", "SUM(unidades)", 0, False),
    ("Coste Ventas", "SUM(unidades * precio_coste)", 2, False),
    ("Margen", "[Ventas Importe] - [Coste Ventas]", 2, False),
    ("Margen %", "[Margen] / [Ventas Importe]", 2, True),
    ("Ventas Mes Anterior", "SUM(importe) de noviembre", 2, False),
    (
        "Var % vs Mes Anterior",
        "(importe diciembre - importe noviembre) / importe noviembre",
        2,
        True,
    ),
    ("Stock Actual (uds)", "SUM(stock_final) del último día", 0, False),
    ("Valor Stock", "SUM(stock_final * precio_coste) del último día", 2, False),
    ("Stock Medio", "media de SUM(stock_final) por fecha", 2, False),
    ("Valor Stock Medio", "media de SUM(stock_final * precio_coste) por fecha", 2, False),
    ("Venta Media Diaria", "[Unidades Vendidas] / días del calendario", 2, False),
    ("Días de Cobertura", "[Stock Actual (uds)] / [Venta Media Diaria]", 1, False),
    ("Rotación", "[Coste Ventas] / [Valor Stock Medio]", 2, False),
    ("Total Referencias", "productos visibles × tiendas visibles", 0, False),
    ("Referencias en Rotura", "pares con stock del último día = 0", 0, False),
    ("Referencias Bajo Mínimo", "pares con 0 < stock < stock_minimo", 0, False),
    ("Referencias Sobrestock", "pares con stock > stock_maximo", 0, False),
    ("% Disponibilidad", "1 - [Referencias en Rotura] / [Total Referencias]", 2, True),
    ("Estado Stock", "solo con un producto y una tienda; si no, blanco", None, False),
)


def cargar():
    """Lee las seis tablas que ve el modelo. El calendario no filtra los hechos."""
    productos = pd.read_csv(RAW / "productos.csv")
    categorias = pd.read_csv(RAW / "categorias.csv")
    tiendas = pd.read_csv(RAW / "tiendas.csv")
    calendario = pd.read_csv(RAW / "calendario.csv", parse_dates=["fecha"])
    ventas = pd.read_csv(RAW / "ventas.csv", parse_dates=["fecha"])
    stock = pd.read_csv(RAW / "stock_diario.csv", parse_dates=["fecha"])
    # La categoría llega a la venta por el producto, igual que la relación del modelo.
    productos = productos.merge(categorias, on="categoria_id", how="left")
    return productos, tiendas, calendario, ventas, stock


def dividir(numerador, denominador):
    """DIVIDE: blanco si el denominador es 0 o vacío, no un error."""
    if denominador is None or pd.isna(denominador) or denominador == 0:
        return None
    if numerador is None or pd.isna(numerador):
        return None
    return numerador / denominador


def calcular(productos, tiendas, calendario, ventas, stock, tienda_id=None, categoria=None):
    """Un contexto de filtro: tienda y categoría opcionales, año completo siempre.

    El calendario no se recorta por tienda ni por categoría (las relaciones van
    del hecho a la dimensión). LASTDATE del año es el max(fecha) del calendario.
    """
    prods = productos if categoria is None else productos[productos["categoria"] == categoria]
    tiendas_ctx = tiendas if tienda_id is None else tiendas[tiendas["tienda_id"] == tienda_id]
    prod_ids = prods["producto_id"]
    tienda_ids = tiendas_ctx["tienda_id"]

    ventas_ctx = ventas[
        ventas["producto_id"].isin(prod_ids) & ventas["tienda_id"].isin(tienda_ids)
    ].merge(prods[["producto_id", "precio_coste"]], on="producto_id", how="left")
    stock_ctx = stock[
        stock["producto_id"].isin(prod_ids) & stock["tienda_id"].isin(tienda_ids)
    ].merge(prods[["producto_id", "precio_coste", "stock_minimo", "stock_maximo"]], on="producto_id", how="left")

    # VALUES(DimCalendario[fecha]) ve el año, no los días que tuvieron venta.
    fechas = pd.Index(calendario["fecha"].unique())
    n_dias = len(fechas)
    ultimo_dia = fechas.max()

    ventas_importe = ventas_ctx["importe"].sum()
    unidades = ventas_ctx["unidades"].sum()
    # SUMX(FactVentas, unidades * RELATED(precio_coste)), no SUM(coste).
    coste_ventas = (ventas_ctx["unidades"] * ventas_ctx["precio_coste"]).sum()
    margen = ventas_importe - coste_ventas

    # El contraste del mes anterior es diciembre contra noviembre, no el año desplazado.
    importe_dic = ventas_ctx.loc[ventas_ctx["fecha"].dt.month == 12, "importe"].sum()
    importe_nov = ventas_ctx.loc[ventas_ctx["fecha"].dt.month == 11, "importe"].sum()

    stock_ultimo = stock_ctx[stock_ctx["fecha"] == ultimo_dia]
    stock_actual = stock_ultimo["stock_final"].sum()
    valor_stock = (stock_ultimo["stock_final"] * stock_ultimo["precio_coste"]).sum()

    # AVERAGEX sobre cada fecha del calendario. Un día sin filas es blanco y no entra en la media.
    stock_por_dia = stock_ctx.groupby("fecha")["stock_final"].sum().reindex(fechas)
    valor_por_dia = (
        stock_ctx.assign(valor=lambda df: df["stock_final"] * df["precio_coste"])
        .groupby("fecha")["valor"]
        .sum()
        .reindex(fechas)
    )
    stock_medio = stock_por_dia.mean()
    valor_stock_medio = valor_por_dia.mean()

    venta_media = dividir(unidades, n_dias)
    dias_cobertura = dividir(stock_actual, venta_media)
    rotacion = dividir(coste_ventas, valor_stock_medio)

    # CROSSJOIN de los valores visibles, no de las filas del hecho.
    pares = pd.MultiIndex.from_product(
        [prods["producto_id"].unique(), tiendas_ctx["tienda_id"].unique()],
        names=["producto_id", "tienda_id"],
    )
    total = len(pares)
    cierre = stock_ultimo.set_index(["producto_id", "tienda_id"])["stock_final"].reindex(pares)
    ficha = prods.drop_duplicates("producto_id").set_index("producto_id")
    mn = pd.Series(pares.get_level_values("producto_id"), index=pares).map(ficha["stock_minimo"])
    mx = pd.Series(pares.get_level_values("producto_id"), index=pares).map(ficha["stock_maximo"])

    # NOT ISBLANK(s) && s = 0. Un par sin fila de stock no es rotura.
    presente = cierre.notna()
    rotura = int((presente & (cierre == 0)).sum())
    # s > 0 && s < mn: la rotura no cuenta aquí, los estados son excluyentes.
    bajo = int((presente & (cierre > 0) & (cierre < mn)).sum())
    # s > mx. El igual al máximo sigue siendo OK. El blanco no cumple la comparación.
    sobre = int((cierre > mx).sum())

    # HASONEVALUE de producto y de tienda. Si no, la medida devuelve blanco.
    if prods["producto_id"].nunique() == 1 and tiendas_ctx["tienda_id"].nunique() == 1:
        s = cierre.iloc[0]
        if pd.isna(s):
            estado = None
        elif s == 0:
            estado = "Rotura"
        elif s < mn.iloc[0]:
            estado = "Bajo mínimo"
        elif s > mx.iloc[0]:
            estado = "Sobrestock"
        else:
            estado = "OK"
    else:
        estado = None

    return {
        "ultimo_dia": ultimo_dia,
        "n_dias": n_dias,
        "Ventas Importe": ventas_importe,
        "Unidades Vendidas": unidades,
        "Coste Ventas": coste_ventas,
        "Margen": margen,
        "Margen %": dividir(margen, ventas_importe),
        "Ventas Mes Anterior": importe_nov,
        "Var % vs Mes Anterior": dividir(importe_dic - importe_nov, importe_nov),
        "Stock Actual (uds)": stock_actual,
        "Valor Stock": valor_stock,
        "Stock Medio": None if pd.isna(stock_medio) else stock_medio,
        "Valor Stock Medio": None if pd.isna(valor_stock_medio) else valor_stock_medio,
        "Venta Media Diaria": venta_media,
        "Días de Cobertura": dias_cobertura,
        "Rotación": rotacion,
        "Total Referencias": total,
        "Referencias en Rotura": rotura,
        "Referencias Bajo Mínimo": bajo,
        "Referencias Sobrestock": sobre,
        "% Disponibilidad": dividir(total - rotura, total) if total else None,
        "Estado Stock": estado,
    }


def texto(valor, decimales, porcentaje):
    """Punto decimal, sin separador de miles: la misma convención que resultados_kpis.md."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "en blanco"
    if isinstance(valor, str):
        return valor
    if porcentaje:
        return f"{valor * 100:.{decimales}f}%"
    if decimales == 0:
        return f"{valor:.0f}"
    return f"{valor:.{decimales}f}"


def tabla(resultado):
    lineas = [
        "| Medida | Cálculo en pandas (fórmula breve) | Valor esperado | Valor en Power BI (pendiente) |",
        "| --- | --- | ---: | --- |",
    ]
    for nombre, formula, decimales, porcentaje in MEDIDAS:
        lineas.append(
            f"| {nombre} | {formula} | {texto(resultado[nombre], decimales, porcentaje)} | pendiente |"
        )
    return "\n".join(lineas)


def escribir(ctx_a, ctx_b, tiendas):
    nombre_tienda = tiendas.loc[tiendas["tienda_id"] == 1, "nombre"].iloc[0]
    ultimo = ctx_a["ultimo_dia"].strftime("%Y-%m-%d")
    texto_md = f"""# Validación de medidas DAX

Contrasta el cálculo en pandas de cada medida de la tabla `_Medidas` con el valor que devolverá Power BI. Sirve para ver, antes de publicar el informe, si una medida replica la regla (stock semiaditivo, coste a precio de ficha, estados de alerta que no se solapan).

Los datos son sintéticos de la cadena ficticia SportStock. No describen a ninguna enseña real.

La columna **Valor en Power BI** se rellena al abrir el `.pbip` y refrescar el modelo. Aquí queda en pendiente.

Los números usan punto decimal y no llevan separador de miles, como en `resultados_kpis.md`. Un porcentaje ya está en tanto por ciento (es lo que muestra el `formatString` 0.00%). Un blanco esperado se escribe `en blanco`.

El último día del año, cierre de las medidas semiaditivas, es {ultimo}. Ventas Mes Anterior y Var % vs Mes Anterior no se calculan desplazando el año entero: el mes actual de ese contraste es diciembre y el anterior es noviembre. Para rellenarlas en Power BI hay que filtrar el calendario a diciembre de 2025; el resto de medidas se contrasta con el año completo, sin filtro de mes.

## Contexto A: año completo, todas las tiendas y productos

{tabla(ctx_a)}

## Contexto B: tienda 1 ({nombre_tienda}) y categoría Running, año completo

{tabla(ctx_b)}
"""
    SALIDA.write_text(texto_md, encoding="utf-8")


def main():
    productos, tiendas, calendario, ventas, stock = cargar()
    ctx_a = calcular(productos, tiendas, calendario, ventas, stock)
    ctx_b = calcular(
        productos, tiendas, calendario, ventas, stock, tienda_id=1, categoria="Running"
    )
    escribir(ctx_a, ctx_b, tiendas)

    # El estado a fecha de corte del KPI SQL: 1000 referencias, estados excluyentes.
    assert ctx_a["Referencias en Rotura"] == 82
    assert ctx_a["Referencias Bajo Mínimo"] == 162
    assert ctx_a["Referencias Sobrestock"] == 64
    assert ctx_a["Total Referencias"] == 1000


if __name__ == "__main__":
    main()
