# SportStock — Análisis de stock retail

Portfolio de Data & BI de Cesar Fernandez (Barcelona) para una candidatura Data & BI Junior. Analiza el stock de la cadena ficticia SportStock en 2025: rotación, cobertura, roturas y sobrestock, con datos 100% sintéticos. La misma base alimenta los KPI en SQL y el modelo semántico de Power BI, de modo que cada cifra se puede seguir hasta la fórmula.

## Problema de negocio

SportStock tiene cinco tiendas y 200 productos en ocho categorías. El stock es el cierre de cada día, no un movimiento que se sume al año. La venta del día es la demanda que cupo en la estantería, no la demanda entera. Si se suman los cierres, o si se toma la venta por la demanda, el informe mezcla capital inmovilizado, rotura y caja.

El calendario va del 2025-01-01 al 2025-12-31 (365 días; 2025 no es bisiesto). La fecha de corte de cobertura y de estado de stock es ese último día: `MAX(fecha)` de `fact_stock`. Hay 1000 referencias (200 productos × 5 tiendas). Grano, filas y relaciones: [docs/modelo_datos.md](docs/modelo_datos.md).

El informe responde una pregunta por página. Las páginas están en desarrollo: el PBIR de [powerbi/RetailStock.Report/definition.pbir](powerbi/RetailStock.Report/definition.pbir) solo apunta al modelo.

### Visión general de stock

¿Cuánto stock hay al cierre, cuánto vale y qué cobertura da la cadena?

A 31/12/2025 hay 118008 unidades, valoradas a coste de ficha en 2081857.94. La cobertura de la cadena es 74.6 días: stock del último día partido por la venta media diaria del año. No es la ventana de 28 días del KPI SQL, que mira el riesgo de rotura por producto y tienda. Fuente: [docs/validacion_medidas.md](docs/validacion_medidas.md).

### Rotación

¿Cuántas veces se renueva el stock valorado a coste, y qué categoría lo retiene más?

La rotación de la cadena es 4.89 (coste de ventas / valor medio diario de stock a coste). Por categoría, el SQL va de 6.03 en Deportes de raqueta (60.53 días de stock) a 4.02 en Deportes de equipo (90.75 días). Desglose: [docs/resultados_kpis.md](docs/resultados_kpis.md).

### Alertas de stock bajo

¿Qué referencias están en rotura o bajo mínimo el 31/12, y cuáles cubren menos días?

Ese día, 82 referencias están a cero y 162 por debajo del mínimo de ficha. La cobertura más corta, entre las que aún tienen stock y vendieron en los 28 días previos, es 2.75 días: SportStock Diagonal, Piolet básico Montix (MON-0023).

### Ventas por categoría

¿Qué categorías mueven el importe de 2025 y con qué margen?

El importe del año es 14312738.15 y el margen, 25.79%. Montaña es la primera por importe (2379821.13, un 16.63% de la venta, margen 25.89%). Deportes de equipo tiene el margen más alto (27.32%) y el menor peso (9.53%): el porcentaje no dice quién mueve la caja.

## KPIs principales

Año 2025, todas las tiendas y productos. Importe, margen y estado de stock salen de [docs/resultados_kpis.md](docs/resultados_kpis.md). Rotación y disponibilidad salen de [docs/validacion_medidas.md](docs/validacion_medidas.md): son el valor esperado en pandas; la columna de Power BI sigue en pendiente. Punto decimal y sin separador de miles, como en esos documentos. Aquí no se recalcula nada.

Rotación = coste de ventas / valor medio diario de stock a coste. Disponibilidad = 1 − referencias en rotura / 1000. Los cuatro estados son excluyentes y cubren las 1000 referencias: 82 + 162 + 64 + 692.

| KPI | Valor |
| --- | ---: |
| Importe 2025 | 14312738.15 |
| Margen % | 25.79% |
| Rotación | 4.89 |
| Disponibilidad | 91.80% |
| Rotura a 31/12 | 82 (8.20%) |
| Bajo mínimo a 31/12 | 162 (16.20%) |
| Sobrestock a 31/12 | 64 (6.40%) |

Importe, margen, rotación y disponibilidad son del año; el cierre semiaditivo de las medidas de stock es el 31/12. Rotura, bajo mínimo y sobrestock son el estado a esa fecha de corte, no la media del año. OK, el cuarto estado, son 692 referencias (69.20%).

## Stack

- **Python.** pandas, numpy y pytest ([requirements.txt](requirements.txt)). Generan los CSV, los tests y el contraste de medidas.
- **SQLite y SQL.** Esquema en estrella, carga con `sqlite3` de la librería estándar y consultas con CTE y funciones de ventana (`SUM() OVER`, `LAG`, `ROW_NUMBER`). No hay SQLAlchemy.
- **Power BI.** Proyecto PBIP, modelo en TMDL, medidas DAX y particiones de Power Query. La cultura del modelo es `es-ES`.
- **Git.** El TMDL es texto: medidas y relaciones se versionan. Los CSV de `data/raw/` también. La base `*.db` no.
- **OpenCode.** Asistente usado para generar código. En el repositorio queda lo revisado a mano ([docs/decisiones.md](docs/decisiones.md)).

## Estructura del repositorio

```
.
├── src
│   ├── generate_data.py       # universo sintético, semilla fija
│   └── validar_medidas.py     # réplica en pandas de las medidas DAX
├── tests
│   ├── conftest.py
│   └── test_generate_data.py  # contrato del generador
├── sql
│   ├── schema.sql             # estrella y claves foráneas
│   ├── load.py                # CSV → data/retail_stock.db
│   ├── kpis.sql               # un bloque por KPI
│   └── run_kpis.py            # escribe docs/resultados_kpis.md
├── data
│   ├── raw                    # seis CSV: dimensiones y hechos
│   └── retail_stock.db        # salida local de load.py; no se versiona
├── powerbi
│   ├── RetailStock.pbip
│   ├── RetailStock.SemanticModel   # tablas, relaciones, DAX, RutaDatos
│   └── RetailStock.Report          # PBIR; páginas aún sin construir
├── docs                       # modelo, medidas, validación, decisiones, KPIs
├── requirements.txt
└── pytest.ini
```

En `data/raw/`, según [docs/modelo_datos.md](docs/modelo_datos.md): `categorias.csv` (8 filas), `productos.csv` (200), `tiendas.csv` (5), `calendario.csv` (365), `ventas.csv` (224317, solo unidades > 0) y `stock_diario.csv` (365000 = 365 × 200 × 5).

## Cómo reproducirlo en Windows

Desde la raíz del repositorio, con Python 3 en el PATH. Power BI Desktop solo hace falta para el último paso.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src\generate_data.py
python -m pytest
python sql\load.py
python sql\run_kpis.py
```

`python src\generate_data.py` regenera los seis CSV en `data\raw\`. La semilla es fija: la misma ejecución produce los mismos ficheros. `python -m pytest` usa [pytest.ini](pytest.ini), que añade `src` al `pythonpath`. `python sql\load.py` borra y recrea `data\retail_stock.db` con [sql/schema.sql](sql/schema.sql). `python sql\run_kpis.py` vuelve a escribir [docs/resultados_kpis.md](docs/resultados_kpis.md) a partir de [sql/kpis.sql](sql/kpis.sql).

Abrir [powerbi/RetailStock.pbip](powerbi/RetailStock.pbip) con Power BI Desktop. Ajustar el parámetro **RutaDatos** si la carpeta de los CSV no es la de este equipo —tiene que terminar en `\`— y pulsar **Actualizar**. Cómo cambiarlo: [docs/configurar_ruta_datos.md](docs/configurar_ruta_datos.md). Al abrir el `.pbip`, Desktop puede pedir activar las características en versión preliminar de PBIP/TMDL.

## Modelo y medidas

Estrella con un copo de un salto. `FactVentas` y `FactStock` comparten el grano fecha-tienda-producto y no se relacionan entre sí: se cruzan por las dimensiones. `DimCalendario` es la tabla de fechas. `DimCategoria` cuelga de `DimProducto`; un filtro de sección llega a la venta y al stock pasando por el producto. Las relaciones son 1:* y de una sola dirección. Si el filtro fuera doble, una venta recortaría el stock y ocultaría referencias sin venta, que son las que la alerta de rotura tiene que ver.

`stock_final` se suma entre tiendas y productos, no entre fechas. Las medidas de stock no hacen `SUM` del periodo: el actual se queda en el último día visible y el medio promedia los cierres diarios. Las medidas viven en la tabla vacía `_Medidas` (ventas, stock y alertas). El contraste, medida a medida, está calculado en pandas y pendiente de Power BI.

- Modelo, grano y relaciones: [docs/modelo_datos.md](docs/modelo_datos.md)
- Definición DAX: [docs/medidas_dax.md](docs/medidas_dax.md)
- Contraste con pandas: [docs/validacion_medidas.md](docs/validacion_medidas.md)
- Decisiones y alternativas: [docs/decisiones.md](docs/decisiones.md)
- KPIs SQL del año: [docs/resultados_kpis.md](docs/resultados_kpis.md)

## Capturas

Las capturas del informe se añadirán en `docs/capturas/` cuando las páginas estén construidas en Power BI Desktop. Este README no enlaza imágenes: esa carpeta todavía no tiene ficheros.

## Estado del proyecto

Terminados: los datos sintéticos, los tests del generador, la capa SQL (esquema, carga y KPIs) y el modelo semántico (tablas, relaciones, parámetro `RutaDatos` y medidas DAX).

El modelo se ha validado con la librería TOM. Las medidas se han validado con pandas, en el año completo y en un segundo contexto (tienda SportStock Diagonal y categoría Running). Falta validarlo abriendo el `.pbip` en Power BI Desktop y rellenar la columna «Valor en Power BI» de [docs/validacion_medidas.md](docs/validacion_medidas.md). Las páginas del informe están en desarrollo.

## Aprendizajes

- **Semiaditividad del stock.** El cierre no se suma a lo largo del calendario: la misma unidad se contaría una vez por cada día que sigue en tienda. Un periodo tiene un último día, no un stock total.
- **Venta perdida frente a demanda.** La venta del día es el mínimo entre la demanda y el stock tras las entradas. Lo que no está en la estantería se pierde; no queda como pedido pendiente. Las unidades vendidas no son la demanda.
- **PBIP y TMDL en Git.** Un `.pbix` no deja leer la medida ni la relación. El TMDL es texto: se compara y se versiona. El informe puede esperar con las páginas sin hacer; el modelo, no.
- **Cultura en Power Query.** El CSV usa punto decimal. Tipar las columnas con la cultura `es-ES` del modelo lee el punto como separador de miles y el importe sale mal. El paso de tipos usa `en-US`; el informe sigue en español.
- **Validar las medidas contra pandas.** Cada medida tiene un valor esperado sobre los CSV, antes de abrir Desktop. Así se comprueba la regla (cierre semiaditivo, coste a precio de ficha, estados que no se solapan) y no solo el visual.

## Nota

Datos sintéticos de la cadena ficticia SportStock, con fines de demostración. No describen a ninguna enseña real.

Autor: Cesar Fernandez.
