"""Tests del generador de datos sintéticos de SportStock.

La fixture de módulo llama a ``generar_datos(seed=42)`` una sola vez: la
simulación es determinista, pero no hace falta repetirla en cada comprobación.
La reproducibilidad sí llama al generador aparte, porque eso es precisamente
lo que tiene que demostrar.
"""

from __future__ import annotations

import pandas as pd
import pytest

from generate_data import generar_datos, guardar_csv

COLUMNAS = {
    "categorias": ["categoria_id", "categoria", "seccion"],
    "productos": [
        "producto_id",
        "sku",
        "nombre",
        "categoria_id",
        "marca",
        "precio_coste",
        "precio_venta",
        "stock_minimo",
        "stock_maximo",
        "lead_time_dias",
    ],
    "tiendas": ["tienda_id", "nombre", "ciudad", "tipo", "m2"],
    "calendario": [
        "fecha",
        "año",
        "mes",
        "nombre_mes",
        "semana",
        "dia_semana",
        "es_fin_de_semana",
        "temporada",
        "es_rebajas",
        "es_black_friday",
    ],
    "ventas": [
        "venta_id",
        "fecha",
        "tienda_id",
        "producto_id",
        "unidades",
        "importe",
        "coste",
    ],
    "stock_diario": [
        "fecha",
        "tienda_id",
        "producto_id",
        "stock_final",
        "entradas",
        "salidas",
    ],
}

CATEGORIAS_ESPERADAS = {
    "Running",
    "Fitness",
    "Ciclismo",
    "Montaña",
    "Deportes de raqueta",
    "Natación",
    "Deportes de equipo",
    "Esquí",
}

CIUDADES_ESPERADAS = {
    "Barcelona",
    "L'Hospitalet de Llobregat",
    "Badalona",
    "Sabadell",
    "Terrassa",
}


@pytest.fixture(scope="module")
def tablas() -> dict[str, pd.DataFrame]:
    """Dataset de referencia (semilla 42), compartido por los tests del módulo."""
    return generar_datos(seed=42)


def test_existen_las_seis_tablas_con_sus_columnas(tablas: dict[str, pd.DataFrame]) -> None:
    assert set(tablas) == set(COLUMNAS)
    for nombre, columnas in COLUMNAS.items():
        assert list(tablas[nombre].columns) == columnas


def test_numero_de_filas(tablas: dict[str, pd.DataFrame]) -> None:
    assert len(tablas["categorias"]) == 8
    assert len(tablas["productos"]) == 200
    assert len(tablas["tiendas"]) == 5
    assert len(tablas["calendario"]) == 365
    assert len(tablas["stock_diario"]) == 5 * 200 * 365
    assert set(tablas["categorias"]["categoria"]) == CATEGORIAS_ESPERADAS
    assert set(tablas["tiendas"]["ciudad"]) == CIUDADES_ESPERADAS
    assert set(tablas["tiendas"]["tipo"]) <= {"grande", "ciudad"}


def test_claves_primarias_unicas(tablas: dict[str, pd.DataFrame]) -> None:
    assert tablas["categorias"]["categoria_id"].is_unique
    assert tablas["productos"]["producto_id"].is_unique
    assert tablas["productos"]["sku"].is_unique
    assert tablas["tiendas"]["tienda_id"].is_unique
    assert tablas["calendario"]["fecha"].is_unique
    assert tablas["ventas"]["venta_id"].is_unique
    assert not tablas["ventas"].duplicated(["fecha", "tienda_id", "producto_id"]).any()
    assert not tablas["stock_diario"].duplicated(["fecha", "tienda_id", "producto_id"]).any()


def test_claves_foraneas(tablas: dict[str, pd.DataFrame]) -> None:
    categorias = set(tablas["categorias"]["categoria_id"])
    tiendas = set(tablas["tiendas"]["tienda_id"])
    productos = set(tablas["productos"]["producto_id"])
    fechas = set(tablas["calendario"]["fecha"])

    assert set(tablas["productos"]["categoria_id"]) <= categorias
    for nombre in ("ventas", "stock_diario"):
        tabla = tablas[nombre]
        assert set(tabla["tienda_id"]) <= tiendas
        assert set(tabla["producto_id"]) <= productos
        assert set(tabla["fecha"]) <= fechas


def test_restricciones_de_dominio(tablas: dict[str, pd.DataFrame]) -> None:
    productos = tablas["productos"]
    ventas = tablas["ventas"]
    stock = tablas["stock_diario"]

    assert (productos["precio_venta"] > productos["precio_coste"]).all()
    assert (productos["stock_minimo"] < productos["stock_maximo"]).all()
    assert productos["lead_time_dias"].between(2, 21).all()
    assert (ventas["unidades"] > 0).all()
    assert (ventas["importe"] >= 0).all()
    assert (ventas["coste"] >= 0).all()
    assert (stock["stock_final"] >= 0).all()
    assert (stock["entradas"] >= 0).all()
    assert (stock["salidas"] >= 0).all()


def test_coherencia_ventas_y_salidas(tablas: dict[str, pd.DataFrame]) -> None:
    """Cada venta es una salida, y no hay salidas sin su fila de venta."""
    cruzado = tablas["stock_diario"].merge(
        tablas["ventas"],
        on=["fecha", "tienda_id", "producto_id"],
        how="left",
        indicator=True,
    )
    con_venta = cruzado["_merge"] == "both"
    sin_venta = cruzado["_merge"] == "left_only"
    assert int(con_venta.sum()) == len(tablas["ventas"])
    assert (cruzado.loc[con_venta, "salidas"] == cruzado.loc[con_venta, "unidades"]).all()
    assert (cruzado.loc[sin_venta, "salidas"] == 0).all()


def test_ecuacion_de_stock(tablas: dict[str, pd.DataFrame]) -> None:
    """stock_final(d) = stock_final(d-1) + entradas(d) - salidas(d), desde el día 2."""
    stock = (
        tablas["stock_diario"]
        .sort_values(["tienda_id", "producto_id", "fecha"])
        .reset_index(drop=True)
    )
    previo = stock.groupby(["tienda_id", "producto_id"], sort=False)["stock_final"].shift(1)
    mascara = previo.notna()
    esperado = previo[mascara] + stock.loc[mascara, "entradas"] - stock.loc[mascara, "salidas"]
    obtenido = stock.loc[mascara, "stock_final"]
    # 1000 combinaciones x 364 transiciones: el 1 de enero no tiene día anterior.
    assert int(mascara.sum()) == 5 * 200 * 364
    assert (obtenido.to_numpy() == esperado.to_numpy()).all()


def test_hay_roturas_y_sobrestock(tablas: dict[str, pd.DataFrame]) -> None:
    stock = tablas["stock_diario"]
    assert (stock["stock_final"] == 0).any()
    maximos = tablas["productos"].set_index("producto_id")["stock_maximo"]
    stock_maximo = stock["producto_id"].map(maximos)
    assert (stock["stock_final"] > stock_maximo).any()


def test_estacionalidad(tablas: dict[str, pd.DataFrame]) -> None:
    ventas = tablas["ventas"].copy()
    ventas["fecha"] = pd.to_datetime(ventas["fecha"])
    productos = tablas["productos"].merge(tablas["categorias"], on="categoria_id")
    ventas = ventas.merge(productos[["producto_id", "categoria"]], on="producto_id")

    noviembre = ventas[ventas["fecha"].dt.month == 11]
    media_noviembre = noviembre["unidades"].sum() / 30
    unidades_bf = noviembre.loc[
        noviembre["fecha"] == pd.Timestamp("2025-11-28"), "unidades"
    ].sum()
    assert unidades_bf > media_noviembre

    running = ventas[ventas["categoria"] == "Running"]
    abril = running.loc[running["fecha"].dt.month == 4, "unidades"].sum()
    diciembre = running.loc[running["fecha"].dt.month == 12, "unidades"].sum()
    assert abril > diciembre

    esqui = ventas[ventas["categoria"] == "Esquí"]
    enero = esqui.loc[esqui["fecha"].dt.month == 1, "unidades"].sum()
    julio = esqui.loc[esqui["fecha"].dt.month == 7, "unidades"].sum()
    assert enero > julio


def test_calendario_de_negocio(tablas: dict[str, pd.DataFrame]) -> None:
    """Ancla las reglas de calendario que luego mueven demanda y descuento."""
    cal = tablas["calendario"].set_index("fecha")
    assert tablas["calendario"]["año"].eq(2025).all()
    assert cal.loc["2025-01-01", "dia_semana"] == "miércoles"
    assert cal.loc["2025-01-01", "nombre_mes"] == "enero"
    assert cal.loc["2025-01-01", "temporada"] == "Invierno"
    assert bool(cal.loc["2025-01-01", "es_fin_de_semana"]) is False
    assert bool(cal.loc["2025-01-04", "es_fin_de_semana"]) is True
    assert bool(cal.loc["2025-01-06", "es_rebajas"]) is False
    assert bool(cal.loc["2025-01-07", "es_rebajas"]) is True
    assert bool(cal.loc["2025-07-01", "es_rebajas"]) is True
    assert bool(cal.loc["2025-07-31", "es_rebajas"]) is True
    assert bool(cal.loc["2025-06-30", "es_rebajas"]) is False
    assert bool(cal.loc["2025-11-28", "es_black_friday"]) is True
    assert cal.loc["2025-11-28", "dia_semana"] == "viernes"
    assert bool(cal.loc["2025-11-27", "es_black_friday"]) is False
    assert set(tablas["calendario"]["temporada"]) == {
        "Invierno",
        "Primavera",
        "Verano",
        "Otoño",
    }


def test_reproducibilidad() -> None:
    primera = generar_datos(seed=42)
    segunda = generar_datos(seed=42)
    for nombre in primera:
        pd.testing.assert_frame_equal(primera[nombre], segunda[nombre])
    otra_semilla = generar_datos(seed=7)
    # Categorías, tiendas y calendario no dependen de la semilla; el hecho sí.
    assert not primera["ventas"].equals(otra_semilla["ventas"])
    assert not primera["stock_diario"].equals(otra_semilla["stock_diario"])
    assert not primera["productos"].equals(otra_semilla["productos"])


def test_guardar_csv(tablas: dict[str, pd.DataFrame], tmp_path: object) -> None:
    guardar_csv(tablas, tmp_path)
    for nombre, columnas in COLUMNAS.items():
        ruta = tmp_path / f"{nombre}.csv"
        assert ruta.is_file()
        releido = pd.read_csv(ruta, encoding="utf-8")
        assert list(releido.columns) == columnas
        assert len(releido) == len(tablas[nombre])
