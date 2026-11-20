-- Consultas de KPI del modelo en estrella de SportStock.
-- Cada bloque es independiente: run_kpis.py corta por la línea "-- KPI:"
-- y ejecuta el SELECT solo. No hay tablas temporales compartidas.
--
-- Fecha de corte = MAX(fecha) de fact_stock. En este extracto es 2025-12-31,
-- pero no se hardcodea: si el calendario cambia, las consultas de corte siguen.
-- El margen % es sobre venta, (importe - coste) / importe. El markup de la
-- ficha (precio_venta / precio_coste - 1) es otra cosa y no se usa aquí.
-- División siempre con literal real (.0): en SQLite 5/2 es 2.

-- KPI: Resumen global
-- Qué mide: la cuenta comercial del año completo, al grano fecha-tienda-producto.
-- Fórmula: margen_bruto = SUM(importe) - SUM(coste); margen_pct = margen_bruto / SUM(importe) * 100.
-- Por qué: es el denominador del resto. Sin esta fila no se sabe si un corte por categoría mueve la caja o solo el porcentaje.

WITH totales AS (
    SELECT
        SUM(importe) AS importe,
        SUM(unidades) AS unidades,
        SUM(coste) AS coste
    FROM fact_ventas
)
SELECT
    importe,
    unidades,
    coste,
    importe - coste AS margen_bruto,
    (importe - coste) * 100.0 / NULLIF(importe, 0) AS margen_pct
FROM totales;

-- KPI: Margen por categoría
-- Qué mide: importe, coste y margen % de cada categoría, y qué peso tiene en la venta.
-- Fórmula: margen_pct = (SUM(importe) - SUM(coste)) / SUM(importe) * 100; peso_importe_pct = importe / SUM(importe) OVER () * 100.
-- Por qué: el margen global esconde una categoría que vende mucho con poco margen. Ordenar por importe pone arriba lo que mueve la caja, no la que más porcentaje saca de un ticket pequeño.

WITH por_categoria AS (
    SELECT
        c.categoria_id,
        c.categoria,
        c.seccion,
        SUM(v.importe) AS importe,
        SUM(v.coste) AS coste
    FROM fact_ventas AS v
    JOIN dim_producto AS p ON p.producto_id = v.producto_id
    JOIN dim_categoria AS c ON c.categoria_id = p.categoria_id
    GROUP BY c.categoria_id, c.categoria, c.seccion
)
SELECT
    categoria,
    seccion,
    importe,
    coste,
    importe - coste AS margen_bruto,
    (importe - coste) * 100.0 / NULLIF(importe, 0) AS margen_pct,
    importe * 100.0 / SUM(importe) OVER () AS peso_importe_pct
FROM por_categoria
ORDER BY importe DESC, categoria;

-- KPI: Rotación anual por categoría
-- Qué mide: cuántas veces se renueva al año el stock de la categoría, valorado a coste, y cuántos días de venta equivale eso.
-- Fórmula: valor_dia = SUM(stock_final * precio_coste) por categoría y fecha; valor_medio_stock = AVG(valor_dia); rotacion = SUM(coste de ventas) / valor_medio_stock; dias_stock = 365 / rotacion.
-- Por qué: es el cociente que pide el enunciado (coste de ventas / stock medio diario a coste). El margen dice si se gana; la rotación dice si el dinero está quieto. 365 y no 366 porque 2025 no es bisiesto y el divisor está fijado. dias_observados tiene que salir 365: si no, la media no es el año entero.

WITH valor_diario AS (
    SELECT
        s.fecha,
        c.categoria_id,
        c.categoria,
        SUM(s.stock_final * p.precio_coste) AS valor_stock
    FROM fact_stock AS s
    JOIN dim_producto AS p ON p.producto_id = s.producto_id
    JOIN dim_categoria AS c ON c.categoria_id = p.categoria_id
    GROUP BY s.fecha, c.categoria_id, c.categoria
),
stock_medio AS (
    SELECT
        categoria_id,
        categoria,
        AVG(valor_stock) AS valor_medio_stock,
        COUNT(*) AS dias_observados
    FROM valor_diario
    GROUP BY categoria_id, categoria
),
coste_ventas AS (
    SELECT
        p.categoria_id,
        SUM(v.coste) AS coste_ventas
    FROM fact_ventas AS v
    JOIN dim_producto AS p ON p.producto_id = v.producto_id
    GROUP BY p.categoria_id
)
SELECT
    sm.categoria,
    cv.coste_ventas,
    sm.valor_medio_stock,
    sm.dias_observados,
    cv.coste_ventas / NULLIF(sm.valor_medio_stock, 0) AS rotacion,
    365.0 * sm.valor_medio_stock / NULLIF(cv.coste_ventas, 0) AS dias_stock,
    RANK() OVER (
        ORDER BY cv.coste_ventas / NULLIF(sm.valor_medio_stock, 0) DESC
    ) AS puesto_rotacion
FROM stock_medio AS sm
JOIN coste_ventas AS cv ON cv.categoria_id = sm.categoria_id
ORDER BY puesto_rotacion, sm.categoria;

-- KPI: Cobertura mínima (15 producto-tienda)
-- Qué mide: las 15 combinaciones producto-tienda con menos días de cobertura a fecha de corte, entre las que aún tienen stock.
-- Fórmula: dias_cobertura = stock_final(fecha de corte) / (unidades vendidas en los 28 días que acaban en esa fecha / 28).
-- Por qué: es el riesgo de rotura de la semana que viene. La media divide por 28 días de calendario, no por los días con venta: si no, un artículo que vende un día y descansa 27 parecería cubrir menos de lo que cubre. Se exige stock_final > 0 (con stock 0 la cobertura es 0 y no informa) y unidades_28 > 0 (sin venta la cobertura no es finita; esa cola está en el KPI de máximos). La ventana sale de dim_calendario, no de un date() hardcodeado. El mismo cálculo está repetido en el KPI de máximos porque cada bloque se ejecuta solo.

WITH corte AS (
    SELECT MAX(fecha) AS fecha_corte
    FROM fact_stock
),
ventana AS (
    SELECT cal.fecha
    FROM dim_calendario AS cal
    JOIN corte ON cal.fecha <= corte.fecha_corte
    ORDER BY cal.fecha DESC
    LIMIT 28
),
ventas_ventana AS (
    SELECT
        v.tienda_id,
        v.producto_id,
        SUM(v.unidades) AS unidades_28
    FROM fact_ventas AS v
    WHERE v.fecha IN (SELECT fecha FROM ventana)
    GROUP BY v.tienda_id, v.producto_id
),
cobertura AS (
    SELECT
        t.nombre AS tienda,
        t.ciudad,
        c.categoria,
        p.sku,
        p.nombre AS producto,
        s.stock_final,
        COALESCE(vv.unidades_28, 0) AS unidades_28,
        COALESCE(vv.unidades_28, 0) * 1.0 / (SELECT COUNT(*) FROM ventana) AS venta_media_diaria,
        s.stock_final / (vv.unidades_28 * 1.0 / (SELECT COUNT(*) FROM ventana)) AS dias_cobertura
    FROM fact_stock AS s
    JOIN corte ON s.fecha = corte.fecha_corte
    JOIN dim_producto AS p ON p.producto_id = s.producto_id
    JOIN dim_categoria AS c ON c.categoria_id = p.categoria_id
    JOIN dim_tienda AS t ON t.tienda_id = s.tienda_id
    JOIN ventas_ventana AS vv
        ON vv.tienda_id = s.tienda_id
       AND vv.producto_id = s.producto_id
    WHERE s.stock_final > 0
      AND vv.unidades_28 > 0
),
ordenada AS (
    SELECT
        cobertura.*,
        ROW_NUMBER() OVER (
            ORDER BY dias_cobertura ASC, stock_final ASC, sku, tienda
        ) AS puesto
    FROM cobertura
)
SELECT
    puesto,
    tienda,
    ciudad,
    categoria,
    sku,
    producto,
    stock_final,
    unidades_28,
    venta_media_diaria,
    dias_cobertura
FROM ordenada
WHERE puesto <= 15
ORDER BY puesto;

-- KPI: Cobertura máxima (15 producto-tienda)
-- Qué mide: las 15 combinaciones producto-tienda con más días de cobertura a fecha de corte y stock por encima de cero.
-- Fórmula: la misma que la cobertura mínima. Si no hubo venta en los 28 días, dias_cobertura queda nulo (no es un número finito) y esa fila va delante: es la cobertura más alta posible.
-- Por qué: es la otra cola del mismo indicador. Sirve para ver stock parado, no solo rotura inminente. El desempate entre las que no vendieron es el stock_final, para que arriba quede la caja inmovilizada y no un empate arbitrario. Se repite la ventana a propósito: este SELECT no ve las CTE del bloque anterior.

WITH corte AS (
    SELECT MAX(fecha) AS fecha_corte
    FROM fact_stock
),
ventana AS (
    SELECT cal.fecha
    FROM dim_calendario AS cal
    JOIN corte ON cal.fecha <= corte.fecha_corte
    ORDER BY cal.fecha DESC
    LIMIT 28
),
ventas_ventana AS (
    SELECT
        v.tienda_id,
        v.producto_id,
        SUM(v.unidades) AS unidades_28
    FROM fact_ventas AS v
    WHERE v.fecha IN (SELECT fecha FROM ventana)
    GROUP BY v.tienda_id, v.producto_id
),
cobertura AS (
    SELECT
        t.nombre AS tienda,
        t.ciudad,
        c.categoria,
        p.sku,
        p.nombre AS producto,
        s.stock_final,
        COALESCE(vv.unidades_28, 0) AS unidades_28,
        COALESCE(vv.unidades_28, 0) * 1.0 / (SELECT COUNT(*) FROM ventana) AS venta_media_diaria,
        CASE
            WHEN COALESCE(vv.unidades_28, 0) = 0 THEN NULL
            ELSE s.stock_final / (vv.unidades_28 * 1.0 / (SELECT COUNT(*) FROM ventana))
        END AS dias_cobertura
    FROM fact_stock AS s
    JOIN corte ON s.fecha = corte.fecha_corte
    JOIN dim_producto AS p ON p.producto_id = s.producto_id
    JOIN dim_categoria AS c ON c.categoria_id = p.categoria_id
    JOIN dim_tienda AS t ON t.tienda_id = s.tienda_id
    LEFT JOIN ventas_ventana AS vv
        ON vv.tienda_id = s.tienda_id
       AND vv.producto_id = s.producto_id
    WHERE s.stock_final > 0
),
ordenada AS (
    SELECT
        cobertura.*,
        ROW_NUMBER() OVER (
            ORDER BY
                CASE WHEN unidades_28 = 0 THEN 1 ELSE 0 END DESC,
                dias_cobertura DESC,
                stock_final DESC,
                sku,
                tienda
        ) AS puesto
    FROM cobertura
)
SELECT
    puesto,
    tienda,
    ciudad,
    categoria,
    sku,
    producto,
    stock_final,
    unidades_28,
    venta_media_diaria,
    dias_cobertura
FROM ordenada
WHERE puesto <= 15
ORDER BY puesto;

-- KPI: Estado de stock a fecha de corte
-- Qué mide: cuántas combinaciones producto-tienda están en rotura, bajo mínimo, sobrestock u OK el último día, en total y por categoría.
-- Fórmula: Rotura = stock_final = 0; Bajo mínimo = 0 < stock_final < stock_minimo; Sobrestock = stock_final > stock_maximo; OK = el resto (stock_minimo <= stock_final <= stock_maximo).
-- Por qué: los cuatro estados son excluyentes y cubren todas las referencias, así que sus porcentajes suman 100. Los umbrales salen de dim_producto (la ficha), no de un flag del hecho. El total dice el tamaño del problema; la categoría dice dónde mirar. TOTAL va al final para no romper el orden alfabético del desglose.

WITH corte AS (
    SELECT MAX(fecha) AS fecha_corte
    FROM fact_stock
),
clasificado AS (
    SELECT
        c.categoria,
        CASE
            WHEN s.stock_final = 0 THEN 'rotura'
            WHEN s.stock_final < p.stock_minimo THEN 'bajo_minimo'
            WHEN s.stock_final > p.stock_maximo THEN 'sobrestock'
            ELSE 'ok'
        END AS estado
    FROM fact_stock AS s
    JOIN corte ON s.fecha = corte.fecha_corte
    JOIN dim_producto AS p ON p.producto_id = s.producto_id
    JOIN dim_categoria AS c ON c.categoria_id = p.categoria_id
),
por_categoria AS (
    SELECT
        categoria,
        SUM(CASE WHEN estado = 'rotura' THEN 1 ELSE 0 END) AS rotura,
        SUM(CASE WHEN estado = 'bajo_minimo' THEN 1 ELSE 0 END) AS bajo_minimo,
        SUM(CASE WHEN estado = 'sobrestock' THEN 1 ELSE 0 END) AS sobrestock,
        SUM(CASE WHEN estado = 'ok' THEN 1 ELSE 0 END) AS ok,
        COUNT(*) AS referencias
    FROM clasificado
    GROUP BY categoria
),
con_total AS (
    SELECT
        categoria,
        referencias,
        rotura,
        bajo_minimo,
        sobrestock,
        ok,
        0 AS es_total
    FROM por_categoria
    UNION ALL
    SELECT
        'TOTAL',
        SUM(referencias),
        SUM(rotura),
        SUM(bajo_minimo),
        SUM(sobrestock),
        SUM(ok),
        1
    FROM por_categoria
)
SELECT
    categoria,
    referencias,
    rotura,
    bajo_minimo,
    sobrestock,
    ok,
    rotura * 100.0 / NULLIF(referencias, 0) AS pct_rotura,
    bajo_minimo * 100.0 / NULLIF(referencias, 0) AS pct_bajo_minimo,
    sobrestock * 100.0 / NULLIF(referencias, 0) AS pct_sobrestock,
    ok * 100.0 / NULLIF(referencias, 0) AS pct_ok
FROM con_total
ORDER BY es_total, categoria;

-- KPI: Días en rotura por categoría
-- Qué mide: cuántos días estuvo en rotura una referencia media de la categoría, y qué porcentaje de los días-referencia del año acabó a cero.
-- Fórmula: dias_referencia = filas de fact_stock de la categoría (producto-tienda-día); dias_referencia_en_rotura = las que tienen stock_final = 0; dias_rotura_medio = dias_referencia_en_rotura / referencias; pct_dias_referencia_rotura = dias_referencia_en_rotura / dias_referencia * 100.
-- Por qué: "días en rotura" como suma de producto-tienda-día pasa de 365 y no se compara entre categorías de distinto tamaño. La media por referencia sí cabe en el año (0-365) y el porcentaje es el que pide el enunciado, sobre el universo de días-referencia y no sobre los días de calendario en los que alguna tienda se quedó a cero.

WITH por_categoria AS (
    SELECT
        c.categoria_id,
        c.categoria,
        COUNT(*) AS dias_referencia,
        SUM(CASE WHEN s.stock_final = 0 THEN 1 ELSE 0 END) AS dias_referencia_en_rotura,
        COUNT(DISTINCT (s.tienda_id * 1000 + s.producto_id)) AS referencias
    FROM fact_stock AS s
    JOIN dim_producto AS p ON p.producto_id = s.producto_id
    JOIN dim_categoria AS c ON c.categoria_id = p.categoria_id
    GROUP BY c.categoria_id, c.categoria
)
SELECT
    categoria,
    referencias,
    dias_referencia_en_rotura,
    dias_referencia,
    dias_referencia_en_rotura * 1.0 / NULLIF(referencias, 0) AS dias_rotura_medio,
    dias_referencia_en_rotura * 100.0 / NULLIF(dias_referencia, 0) AS pct_dias_referencia_rotura,
    dias_referencia_en_rotura * 100.0
        / SUM(dias_referencia_en_rotura) OVER () AS peso_rotura_pct
FROM por_categoria
ORDER BY pct_dias_referencia_rotura DESC, categoria;

-- KPI: Top 3 productos por categoría
-- Qué mide: los tres productos de mayor importe dentro de cada categoría.
-- Fórmula: ROW_NUMBER() OVER (PARTITION BY categoria ORDER BY importe DESC, sku). El sku desempató para que el puesto no dependa del orden de inserción.
-- Por qué: el ranking por categoría evita que una categoría cara (esquí) ocupe todo el top global y deje sin voz al resto. Se ordena la salida por el importe de la categoría, no por el nombre, para que lo que más vende quede arriba si el informe corta filas.

WITH ventas_producto AS (
    SELECT
        c.categoria_id,
        c.categoria,
        p.producto_id,
        p.sku,
        p.nombre,
        p.marca,
        SUM(v.importe) AS importe,
        SUM(v.unidades) AS unidades,
        SUM(v.coste) AS coste
    FROM fact_ventas AS v
    JOIN dim_producto AS p ON p.producto_id = v.producto_id
    JOIN dim_categoria AS c ON c.categoria_id = p.categoria_id
    GROUP BY
        c.categoria_id,
        c.categoria,
        p.producto_id,
        p.sku,
        p.nombre,
        p.marca
),
ranked AS (
    SELECT
        categoria,
        sku,
        nombre,
        marca,
        importe,
        unidades,
        (importe - coste) * 100.0 / NULLIF(importe, 0) AS margen_pct,
        ROW_NUMBER() OVER (
            PARTITION BY categoria_id
            ORDER BY importe DESC, sku
        ) AS puesto,
        SUM(importe) OVER (PARTITION BY categoria_id) AS importe_categoria
    FROM ventas_producto
)
SELECT
    categoria,
    puesto,
    sku,
    nombre,
    marca,
    importe,
    unidades,
    margen_pct,
    importe_categoria
FROM ranked
WHERE puesto <= 3
ORDER BY importe_categoria DESC, categoria, puesto;

-- KPI: Ventas mensuales y variación
-- Qué mide: importe y unidades de cada mes, y la variación % frente al mes anterior.
-- Fórmula: var_pct_importe = (importe - LAG(importe) OVER (ORDER BY mes)) / LAG(importe) * 100. Igual para unidades.
-- Por qué: el mes se toma de dim_calendario, no de un substr de la fecha, para que el nombre del mes salga de la dimensión. Enero no tiene mes anterior dentro del extracto: la variación queda nula, no cero. La de unidades acompaña a la de importe para separar un movimiento de precio (rebajas, Black Friday) de uno de volumen.
WITH por_mes AS (
    SELECT
        cal.mes,
        cal.nombre_mes,
        SUM(v.importe) AS importe,
        SUM(v.unidades) AS unidades
    FROM fact_ventas AS v
    JOIN dim_calendario AS cal ON cal.fecha = v.fecha
    GROUP BY cal.mes, cal.nombre_mes
),
con_lag AS (
    SELECT
        mes,
        nombre_mes,
        importe,
        unidades,
        LAG(importe) OVER (ORDER BY mes) AS importe_anterior,
        LAG(unidades) OVER (ORDER BY mes) AS unidades_anterior
    FROM por_mes
)
SELECT
    mes,
    nombre_mes,
    importe,
    unidades,
    CASE
        WHEN importe_anterior IS NULL OR importe_anterior = 0 THEN NULL
        ELSE (importe - importe_anterior) * 100.0 / importe_anterior
    END AS var_pct_importe,
    CASE
        WHEN unidades_anterior IS NULL OR unidades_anterior = 0 THEN NULL
        ELSE (unidades - unidades_anterior) * 100.0 / unidades_anterior
    END AS var_pct_unidades
FROM con_lag
ORDER BY mes;
