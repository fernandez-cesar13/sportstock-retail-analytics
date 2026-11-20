# Validación de medidas DAX

Contrasta el cálculo en pandas de cada medida de la tabla `_Medidas` con el valor que devolverá Power BI. Sirve para ver, antes de publicar el informe, si una medida replica la regla (stock semiaditivo, coste a precio de ficha, estados de alerta que no se solapan).

Los datos son sintéticos de la cadena ficticia SportStock. No describen a ninguna enseña real.

La columna **Valor en Power BI** se rellena al abrir el `.pbip` y refrescar el modelo. Aquí queda en pendiente.

Los números usan punto decimal y no llevan separador de miles, como en `resultados_kpis.md`. Un porcentaje ya está en tanto por ciento (es lo que muestra el `formatString` 0.00%). Un blanco esperado se escribe `en blanco`.

El último día del año, cierre de las medidas semiaditivas, es 2025-12-31. Ventas Mes Anterior y Var % vs Mes Anterior no se calculan desplazando el año entero: el mes actual de ese contraste es diciembre y el anterior es noviembre. Para rellenarlas en Power BI hay que filtrar el calendario a diciembre de 2025; el resto de medidas se contrasta con el año completo, sin filtro de mes.

## Contexto A: año completo, todas las tiendas y productos

| Medida | Cálculo en pandas (fórmula breve) | Valor esperado | Valor en Power BI (pendiente) |
| --- | --- | ---: | --- |
| Ventas Importe | SUM(importe) | 14312738.15 | pendiente |
| Unidades Vendidas | SUM(unidades) | 577523 | pendiente |
| Coste Ventas | SUM(unidades * precio_coste) | 10621040.87 | pendiente |
| Margen | [Ventas Importe] - [Coste Ventas] | 3691697.28 | pendiente |
| Margen % | [Margen] / [Ventas Importe] | 25.79% | pendiente |
| Ventas Mes Anterior | SUM(importe) de noviembre | 1205039.02 | pendiente |
| Var % vs Mes Anterior | (importe diciembre - importe noviembre) / importe noviembre | 18.64% | pendiente |
| Stock Actual (uds) | SUM(stock_final) del último día | 118008 | pendiente |
| Valor Stock | SUM(stock_final * precio_coste) del último día | 2081857.94 | pendiente |
| Stock Medio | media de SUM(stock_final) por fecha | 122326.19 | pendiente |
| Valor Stock Medio | media de SUM(stock_final * precio_coste) por fecha | 2170030.35 | pendiente |
| Venta Media Diaria | [Unidades Vendidas] / días del calendario | 1582.25 | pendiente |
| Días de Cobertura | [Stock Actual (uds)] / [Venta Media Diaria] | 74.6 | pendiente |
| Rotación | [Coste Ventas] / [Valor Stock Medio] | 4.89 | pendiente |
| Total Referencias | productos visibles × tiendas visibles | 1000 | pendiente |
| Referencias en Rotura | pares con stock del último día = 0 | 82 | pendiente |
| Referencias Bajo Mínimo | pares con 0 < stock < stock_minimo | 162 | pendiente |
| Referencias Sobrestock | pares con stock > stock_maximo | 64 | pendiente |
| % Disponibilidad | 1 - [Referencias en Rotura] / [Total Referencias] | 91.80% | pendiente |
| Estado Stock | solo con un producto y una tienda; si no, blanco | en blanco | pendiente |

## Contexto B: tienda 1 (SportStock Diagonal) y categoría Running, año completo

| Medida | Cálculo en pandas (fórmula breve) | Valor esperado | Valor en Power BI (pendiente) |
| --- | --- | ---: | --- |
| Ventas Importe | SUM(importe) | 678759.89 | pendiente |
| Unidades Vendidas | SUM(unidades) | 23475 | pendiente |
| Coste Ventas | SUM(unidades * precio_coste) | 495389.25 | pendiente |
| Margen | [Ventas Importe] - [Coste Ventas] | 183370.64 | pendiente |
| Margen % | [Margen] / [Ventas Importe] | 27.02% | pendiente |
| Ventas Mes Anterior | SUM(importe) de noviembre | 45991.40 | pendiente |
| Var % vs Mes Anterior | (importe diciembre - importe noviembre) / importe noviembre | -6.55% | pendiente |
| Stock Actual (uds) | SUM(stock_final) del último día | 2483 | pendiente |
| Valor Stock | SUM(stock_final * precio_coste) del último día | 52547.33 | pendiente |
| Stock Medio | media de SUM(stock_final) por fecha | 2089.27 | pendiente |
| Valor Stock Medio | media de SUM(stock_final * precio_coste) por fecha | 46878.49 | pendiente |
| Venta Media Diaria | [Unidades Vendidas] / días del calendario | 64.32 | pendiente |
| Días de Cobertura | [Stock Actual (uds)] / [Venta Media Diaria] | 38.6 | pendiente |
| Rotación | [Coste Ventas] / [Valor Stock Medio] | 10.57 | pendiente |
| Total Referencias | productos visibles × tiendas visibles | 25 | pendiente |
| Referencias en Rotura | pares con stock del último día = 0 | 2 | pendiente |
| Referencias Bajo Mínimo | pares con 0 < stock < stock_minimo | 4 | pendiente |
| Referencias Sobrestock | pares con stock > stock_maximo | 2 | pendiente |
| % Disponibilidad | 1 - [Referencias en Rotura] / [Total Referencias] | 92.00% | pendiente |
| Estado Stock | solo con un producto y una tienda; si no, blanco | en blanco | pendiente |
