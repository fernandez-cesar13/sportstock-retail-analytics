# Medidas DAX

Las 20 medidas están en la tabla `_Medidas` ([`_Medidas.tmdl`](../powerbi/RetailStock.SemanticModel/definition/tables/_Medidas.tmdl)), agrupadas en tres carpetas: Ventas (7), Stock (7) y Alertas (6). La tabla no tiene datos: la partición es un `#table` vacío y la columna `Columna` va oculta. Solo sirve de contenedor.

El contraste con pandas, antes de publicar el informe, está en [validacion_medidas.md](validacion_medidas.md). Con el año completo y sin filtro de tienda ni producto, el cierre semiaditivo es el 2025-12-31. Ventas Mes Anterior y Var % vs Mes Anterior no se leen sobre el año entero: en ese contraste el mes actual es diciembre y el anterior es noviembre.

El DAX de abajo es el del TMDL.

## Conceptos clave

**Semiaditividad y `LASTDATE`.** `stock_final` se suma entre tiendas y productos, no entre días. `LASTDATE(DimCalendario[fecha])` deja en el filtro solo el último día del periodo visible, y `CALCULATE` evalúa el stock en ese cierre. Sumar el año contaría el mismo par producto-tienda una vez por día. Hace falta que `DimCalendario` sea la tabla de fechas: `DATEADD` de Ventas Mes Anterior también lo exige. El porqué del snapshot está en [modelo_datos.md](modelo_datos.md).

**`Valor Stock Medio` es el denominador de la rotación.** Rotación = coste de lo vendido / stock medio a coste. El denominador no es el cierre del último día (ese es `Valor Stock`) ni una media de filas. `AVERAGEX` sobre `VALUES(DimCalendario[fecha])` promedia el cierre de cada día, así un día pesa igual que otro. `Coste Ventas` valora las unidades a `DimProducto[precio_coste]`, el mismo precio que valora el stock: margen y rotación hablan el mismo idioma. No usa `FactVentas[coste]`.

**`CROSSJOIN` de producto × tienda.** Los conteos de alerta no cuentan filas del hecho. Una referencia sin venta sigue siendo una referencia, y FactVentas no tiene fila si no hubo unidades. El universo es el producto cartesiano de los `producto_id` y `tienda_id` visibles. Sin filtro son 200 × 5 = 1.000, el `Total Referencias` del contexto A en [validacion_medidas.md](validacion_medidas.md).

**Estados excluyentes.** Se evalúan sobre el cierre (`Stock Actual`), no sobre la suma del periodo. Un blanco (no hay fila de stock observada) no es rotura.

| Estado | Regla |
| --- | --- |
| Rotura | stock observado = 0 |
| Bajo mínimo | 0 < stock < stock_minimo |
| Sobrestock | stock > stock_maximo |
| OK | stock_minimo ≤ stock ≤ stock_maximo |

En el máximo la referencia sigue OK: el sobrestock es estricto. Bajo mínimo exige `s > 0`, así no pisa la rotura. Los cuatro cubren todas las referencias observadas; sus porcentajes pueden sumar 100. La misma regla, a fecha de corte, está en el KPI de estado de [resultados_kpis.md](resultados_kpis.md).

**`DIVIDE`.** Si el denominador es 0 o vacío, devuelve blanco en vez de un error de división. Margen %, la variación mensual, la venta media, la cobertura y la rotación son un `DIVIDE`: sin venta, o sin stock medio, el visual queda en blanco, no en cero. `% Disponibilidad` resta de 1 la tasa de rotura; el `DIVIDE` interior es el que evita dividir por cero referencias.

`Días de Cobertura` parte el stock del último día por la venta media del periodo filtrado. No usa la ventana fija de 28 días del KPI SQL de [resultados_kpis.md](resultados_kpis.md).

## Ventas

### Ventas Importe

Importe vendido en el periodo, con el descuento ya aplicado en el hecho. No se reconstruye desde `precio_venta`.

Formato: `#,##0.00 €`

```dax
// El importe del hecho ya lleva el descuento; no se recalcula desde precio_venta
SUM ( FactVentas[importe] )
```

### Unidades Vendidas

Unidades que cupieron en el stock. Es la base de la venta media y de la cobertura, no la demanda.

Formato: `#,##0`

```dax
// Unidades reales (la demanda que cupo en el stock), base de la venta media y de la cobertura
SUM ( FactVentas[unidades] )
```

### Coste Ventas

Coste de lo vendido a precio de ficha, no a `FactVentas[coste]`. Así el numerador de la rotación y el valor del stock usan el mismo precio.

Formato: `#,##0.00 €`

```dax
// Precio de ficha, no FactVentas[coste]: el mismo coste que valora el stock, para que margen y rotación hablen el mismo idioma
SUMX (
    FactVentas,
    FactVentas[unidades] * RELATED ( DimProducto[precio_coste] )
)
```

### Margen

Margen bruto del periodo: importe menos coste de ventas. No es el markup de la ficha (`precio_venta / precio_coste - 1`).

Formato: `#,##0.00 €`

```dax
// Margen bruto del periodo. No es el markup de la ficha (precio_venta / precio_coste - 1)
[Ventas Importe] - [Coste Ventas]
```

### Margen %

Margen sobre el importe vendido, no sobre el coste. Sin importe, `DIVIDE` deja el visual en blanco.

Formato: `0.00%`

```dax
// Sobre venta, no sobre coste. DIVIDE deja el visual en blanco si no hubo importe, en vez de un error de división
DIVIDE ( [Margen], [Ventas Importe] )
```

### Ventas Mes Anterior

Importe del mes anterior al periodo filtrado. `DATEADD` desplaza el filtro de fechas un mes; no es el año anterior y exige un rango contiguo en el calendario.

Formato: `#,##0.00 €`

```dax
// DATEADD desplaza el filtro de fechas un mes y exige un rango contiguo en el calendario. No es el año anterior
CALCULATE (
    [Ventas Importe],
    DATEADD ( DimCalendario[fecha], -1, MONTH )
)
```

### Var % vs Mes Anterior

Variación relativa del importe frente al mes anterior. Si ese mes no vendió, `DIVIDE` evita el error.

Formato: `0.00%`

```dax
// Variación relativa. DIVIDE evita el error si el mes anterior no vendió (denominador vacío o cero)
DIVIDE (
    [Ventas Importe] - [Ventas Mes Anterior],
    [Ventas Mes Anterior]
)
```

## Stock

### Stock Actual (uds)

Unidades en stock al último día del periodo. Se suma entre tiendas y productos; `LASTDATE` impide sumar entre días.

Formato: `#,##0`

```dax
// Stock semiaditivo: se suma entre tiendas y productos, pero NO entre días; LASTDATE toma el cierre del último día del periodo filtrado
CALCULATE (
    SUM ( FactStock[stock_final] ),
    LASTDATE ( DimCalendario[fecha] )
)
```

### Valor Stock

El mismo cierre, valorado a `precio_coste`. Sumar el año contaría el mismo par muchas veces.

Formato: `#,##0.00 €`

```dax
// Mismo cierre que Stock Actual, valorado a precio_coste. Sumar el año contaría el mismo par muchas veces
CALCULATE (
    SUMX (
        FactStock,
        FactStock[stock_final] * RELATED ( DimProducto[precio_coste] )
    ),
    LASTDATE ( DimCalendario[fecha] )
)
```

### Stock Medio

Media de los cierres diarios del periodo, no media de filas. Un día con menos combinaciones no pesa menos. `AVERAGEX` ignora el día en blanco. El `formatString` es entero; el contraste con decimales está en [validacion_medidas.md](validacion_medidas.md).

Formato: `#,##0`

```dax
// Media de los cierres diarios, no de las filas: un día con menos combinaciones no debe pesar menos. AVERAGEX ignora el día en blanco
AVERAGEX (
    VALUES ( DimCalendario[fecha] ),
    CALCULATE ( SUM ( FactStock[stock_final] ) )
)
```

### Valor Stock Medio

Media del valor a coste de cada día. Es el denominador de la rotación, no el cierre del último día.

Formato: `#,##0.00 €`

```dax
// Denominador de la rotación: stock medio a coste, no el cierre del último día (ese es Valor Stock)
AVERAGEX (
    VALUES ( DimCalendario[fecha] ),
    CALCULATE (
        SUMX (
            FactStock,
            FactStock[stock_final] * RELATED ( DimProducto[precio_coste] )
        )
    )
)
```

### Venta Media Diaria

Unidades vendidas por día de calendario visible, no por día con venta. Un día sin ticket cuenta; si no, la cobertura sale más corta.

Formato: `#,##0.00`

```dax
// Divide por los días del calendario visibles, no por los días con venta: un día sin ticket cuenta, si no la cobertura sale más corta
DIVIDE (
    [Unidades Vendidas],
    COUNTROWS ( VALUES ( DimCalendario[fecha] ) )
)
```

### Días de Cobertura

Días que cubre el stock del último día al ritmo de venta del periodo filtrado. No es la cobertura a 28 días del KPI SQL.

Formato: `#,##0.0`

```dax
// Stock del último día partido por la venta media del periodo filtrado. No usa la ventana fija de 28 días del KPI SQL
DIVIDE ( [Stock Actual (uds)], [Venta Media Diaria] )
```

### Rotación

Veces que el stock medio a coste se renovó con el coste de ventas. El margen dice si se gana; la rotación dice si el dinero está quieto.

Formato: `#,##0.00`

```dax
// Coste de lo vendido / valor medio del stock. El margen dice si se gana; esto dice si el dinero está quieto
DIVIDE ( [Coste Ventas], [Valor Stock Medio] )
```

## Alertas

### Total Referencias

Combinaciones producto-tienda visibles. No son las filas del hecho: una combinación sin movimiento sigue contando.

Formato: `#,##0`

```dax
// Producto × tienda del contexto, no las filas del hecho: una combinación sin movimiento sigue siendo una referencia
COUNTROWS (
    CROSSJOIN (
        VALUES ( DimProducto[producto_id] ),
        VALUES ( DimTienda[tienda_id] )
    )
)
```

### Referencias en Rotura

Pares producto-tienda con stock a cero el último día. El blanco no es rotura: esa combinación no se observó.

Formato: `#,##0`

```dax
// Se evalúa el cierre (Stock Actual), no la suma del periodo. El blanco (sin fila de stock) no es rotura: no se observó
COUNTROWS (
    FILTER (
        CROSSJOIN (
            VALUES ( DimProducto[producto_id] ),
            VALUES ( DimTienda[tienda_id] )
        ),
        VAR s = [Stock Actual (uds)]
        RETURN
            NOT ISBLANK ( s ) && s = 0
    )
)
```

### Referencias Bajo Mínimo

Pares con stock por encima de cero y por debajo del mínimo de la ficha. `s > 0` deja fuera la rotura. El `CALCULATE` aplica el producto de la fila del `CROSSJOIN`; sin él, `MAX` vería todo el filtro.

Formato: `#,##0`

```dax
// Excluye la rotura (s > 0) para que los estados no se solapen. CALCULATE aplica el producto de la fila: sin él, MAX vería todo el filtro
COUNTROWS (
    FILTER (
        CROSSJOIN (
            VALUES ( DimProducto[producto_id] ),
            VALUES ( DimTienda[tienda_id] )
        ),
        VAR s = [Stock Actual (uds)]
        VAR mn =
            CALCULATE ( MAX ( DimProducto[stock_minimo] ) )
        RETURN
            s > 0 && s < mn
    )
)
```

### Referencias Sobrestock

Pares con stock estrictamente por encima del máximo. En el máximo siguen OK. Un stock en blanco no cumple `s > mx`.

Formato: `#,##0`

```dax
// Estrictamente por encima del máximo: en el máximo la referencia sigue OK. Un stock en blanco no cumple s > mx
COUNTROWS (
    FILTER (
        CROSSJOIN (
            VALUES ( DimProducto[producto_id] ),
            VALUES ( DimTienda[tienda_id] )
        ),
        VAR s = [Stock Actual (uds)]
        VAR mx =
            CALCULATE ( MAX ( DimProducto[stock_maximo] ) )
        RETURN
            s > mx
    )
)
```

### % Disponibilidad

Proporción de referencias que no están en rotura: 1 menos rotura / total. `DIVIDE` evita dividir por cero si el filtro no tiene referencias.

Formato: `0.00%`

```dax
// 1 menos la tasa de rotura. DIVIDE deja blanco si el filtro no tiene referencias, en vez de dividir por cero
1 - DIVIDE ( [Referencias en Rotura], [Total Referencias] )
```

### Estado Stock

Etiqueta de una sola referencia (un producto y una tienda), para formato condicional de una celda. Con varias, `HASONEVALUE` deja la medida en blanco: un texto agregado mentiría. Si el cierre es blanco, también queda en blanco.

Formato: texto, sin `formatString`.

```dax
// Solo para formato condicional de una celda. Con varias referencias un texto agregado mentiría; HASONEVALUE lo deja en blanco
IF (
    HASONEVALUE ( DimProducto[producto_id] )
        && HASONEVALUE ( DimTienda[tienda_id] ),
    VAR s = [Stock Actual (uds)]
    VAR mn =
        MAX ( DimProducto[stock_minimo] )
    VAR mx =
        MAX ( DimProducto[stock_maximo] )
    RETURN
        IF (
            ISBLANK ( s ),
            BLANK (),
            SWITCH (
                TRUE (),
                s = 0, "Rotura",
                s < mn, "Bajo mínimo",
                s > mx, "Sobrestock",
                "OK"
            )
        )
)
```
