# KPIs de stock y ventas — SportStock

Datos 100% sintéticos de la cadena ficticia SportStock. No describen a ninguna enseña real.

Fecha de generación: 2026-11-20 11:31.

Fecha de corte: 2025-12-31 (`MAX(fecha)` de `fact_stock`). Las consultas de cobertura y de estado usan esa fecha; el resto, el año completo.

Los reales se muestran con 2 decimales. Es redondeo de presentación: el cálculo se hace en SQL sin redondear. Un nulo (enero, o cobertura sin venta en 28 días) se escribe `n/d`, no cero.

## Resumen global

> Qué mide: la cuenta comercial del año completo, al grano fecha-tienda-producto.
> Fórmula: margen_bruto = SUM(importe) - SUM(coste); margen_pct = margen_bruto / SUM(importe) * 100.
> Por qué: es el denominador del resto. Sin esta fila no se sabe si un corte por categoría mueve la caja o solo el porcentaje.

| importe | unidades | coste | margen_bruto | margen_pct |
| ---: | ---: | ---: | ---: | ---: |
| 14312738.15 | 577523.00 | 10621040.87 | 3691697.28 | 25.79 |

## Margen por categoría

> Qué mide: importe, coste y margen % de cada categoría, y qué peso tiene en la venta.
> Fórmula: margen_pct = (SUM(importe) - SUM(coste)) / SUM(importe) * 100; peso_importe_pct = importe / SUM(importe) OVER () * 100.
> Por qué: el margen global esconde una categoría que vende mucho con poco margen. Ordenar por importe pone arriba lo que mueve la caja, no la que más porcentaje saca de un ticket pequeño.

| categoria | seccion | importe | coste | margen_bruto | margen_pct | peso_importe_pct |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Montaña | Outdoor | 2379821.13 | 1763737.92 | 616083.21 | 25.89 | 16.63 |
| Esquí | Nieve | 1998246.74 | 1468829.29 | 529417.45 | 26.49 | 13.96 |
| Running | Deportes de resistencia | 1903396.54 | 1390939.91 | 512456.63 | 26.92 | 13.30 |
| Ciclismo | Deportes de resistencia | 1851047.99 | 1402585.47 | 448462.52 | 24.23 | 12.93 |
| Fitness | Deportes de interior | 1831188.94 | 1374297.25 | 456891.69 | 24.95 | 12.79 |
| Deportes de raqueta | Deportes de interior | 1779257.17 | 1326414.50 | 452842.67 | 25.45 | 12.43 |
| Deportes de equipo | Deportes colectivos | 1363582.36 | 991041.80 | 372540.56 | 27.32 | 9.53 |
| Natación | Agua | 1206197.28 | 903194.73 | 303002.55 | 25.12 | 8.43 |

## Rotación anual por categoría

> Qué mide: cuántas veces se renueva al año el stock de la categoría, valorado a coste, y cuántos días de venta equivale eso.
> Fórmula: valor_dia = SUM(stock_final * precio_coste) por categoría y fecha; valor_medio_stock = AVG(valor_dia); rotacion = SUM(coste de ventas) / valor_medio_stock; dias_stock = 365 / rotacion.
> Por qué: es el cociente que pide el enunciado (coste de ventas / stock medio diario a coste). El margen dice si se gana; la rotación dice si el dinero está quieto. 365 y no 366 porque 2025 no es bisiesto y el divisor está fijado. dias_observados tiene que salir 365: si no, la media no es el año entero.

| categoria | coste_ventas | valor_medio_stock | dias_observados | rotacion | dias_stock | puesto_rotacion |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Deportes de raqueta | 1326414.50 | 219976.20 | 365 | 6.03 | 60.53 | 1 |
| Montaña | 1763737.92 | 294984.05 | 365 | 5.98 | 61.05 | 2 |
| Ciclismo | 1402585.47 | 268657.47 | 365 | 5.22 | 69.91 | 3 |
| Running | 1390939.91 | 275779.34 | 365 | 5.04 | 72.37 | 4 |
| Natación | 903194.73 | 190233.24 | 365 | 4.75 | 76.88 | 5 |
| Fitness | 1374297.25 | 314044.46 | 365 | 4.38 | 83.41 | 6 |
| Esquí | 1468829.29 | 359940.25 | 365 | 4.08 | 89.44 | 7 |
| Deportes de equipo | 991041.80 | 246415.34 | 365 | 4.02 | 90.75 | 8 |

## Cobertura mínima (15 producto-tienda)

> Qué mide: las 15 combinaciones producto-tienda con menos días de cobertura a fecha de corte, entre las que aún tienen stock.
> Fórmula: dias_cobertura = stock_final(fecha de corte) / (unidades vendidas en los 28 días que acaban en esa fecha / 28).
> Por qué: es el riesgo de rotura de la semana que viene. La media divide por 28 días de calendario, no por los días con venta: si no, un artículo que vende un día y descansa 27 parecería cubrir menos de lo que cubre. Se exige stock_final > 0 (con stock 0 la cobertura es 0 y no informa) y unidades_28 > 0 (sin venta la cobertura no es finita; esa cola está en el KPI de máximos). La ventana sale de dim_calendario, no de un date() hardcodeado. El mismo cálculo está repetido en el KPI de máximos porque cada bloque se ejecuta solo.

| puesto | tienda | ciudad | categoria | sku | producto | stock_final | unidades_28 | venta_media_diaria | dias_cobertura |
| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| 1 | SportStock Diagonal | Barcelona | Montaña | MON-0023 | Piolet básico Montix | 10 | 102 | 3.64 | 2.75 |
| 2 | SportStock Diagonal | Barcelona | Esquí | ESQ-0018 | Protector de espalda Albor | 12 | 105 | 3.75 | 3.20 |
| 3 | SportStock Sabadell | Sabadell | Esquí | ESQ-0012 | Calcetines de esquí Albor | 22 | 176 | 6.29 | 3.50 |
| 4 | SportStock Diagonal | Barcelona | Montaña | MON-0010 | Cantimplora Montix 1 L | 32 | 225 | 8.04 | 3.98 |
| 5 | SportStock Diagonal | Barcelona | Montaña | MON-0012 | Saco de dormir Montix 10C | 13 | 91 | 3.25 | 4.00 |
| 6 | SportStock Diagonal | Barcelona | Montaña | MON-0008 | Bastón telescópico Montix par | 24 | 155 | 5.54 | 4.34 |
| 7 | SportStock Diagonal | Barcelona | Fitness | FIT-0001 | Mancuerna hexagonal Fitcore 5 kg | 1 | 5 | 0.18 | 5.60 |
| 8 | SportStock Badalona | Badalona | Running | RUN-0021 | Rodilleras running Corrid | 1 | 5 | 0.18 | 5.60 |
| 9 | SportStock Diagonal | Barcelona | Esquí | ESQ-0020 | Calentador de cuello Albor | 25 | 112 | 4.00 | 6.25 |
| 10 | SportStock Diagonal | Barcelona | Esquí | ESQ-0022 | Toalla de nieve Albor | 48 | 202 | 7.21 | 6.65 |
| 11 | SportStock Sabadell | Sabadell | Esquí | ESQ-0019 | Malla térmica Nivex | 29 | 119 | 4.25 | 6.82 |
| 12 | SportStock Diagonal | Barcelona | Ciclismo | CIC-0013 | Bomba de mano Pedalix | 1 | 4 | 0.14 | 7.00 |
| 13 | SportStock Diagonal | Barcelona | Deportes de equipo | EQU-0001 | Balón de fútbol Ludix | 1 | 4 | 0.14 | 7.00 |
| 14 | SportStock Diagonal | Barcelona | Esquí | ESQ-0010 | Pantalón de esquí Albor | 15 | 56 | 2.00 | 7.50 |
| 15 | SportStock Sabadell | Sabadell | Esquí | ESQ-0009 | Chaqueta de esquí Nivex | 14 | 52 | 1.86 | 7.54 |

## Cobertura máxima (15 producto-tienda)

> Qué mide: las 15 combinaciones producto-tienda con más días de cobertura a fecha de corte y stock por encima de cero.
> Fórmula: la misma que la cobertura mínima. Si no hubo venta en los 28 días, dias_cobertura queda nulo (no es un número finito) y esa fila va delante: es la cobertura más alta posible.
> Por qué: es la otra cola del mismo indicador. Sirve para ver stock parado, no solo rotura inminente. El desempate entre las que no vendieron es el stock_final, para que arriba quede la caja inmovilizada y no un empate arbitrario. Se repite la ventana a propósito: este SELECT no ve las CTE del bloque anterior.

| puesto | tienda | ciudad | categoria | sku | producto | stock_final | unidades_28 | venta_media_diaria | dias_cobertura |
| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| 1 | SportStock Gran Via | L'Hospitalet de Llobregat | Deportes de equipo | EQU-0013 | Rodilleras de voleibol Ludix | 5 | 0 | 0.00 | n/d |
| 2 | SportStock Gran Via | L'Hospitalet de Llobregat | Natación | NAT-0001 | Bañador jammer Aqualis | 4 | 0 | 0.00 | n/d |
| 3 | SportStock Sabadell | Sabadell | Running | RUN-0013 | Mochila de hidratación Trailon 5 L | 4 | 0 | 0.00 | n/d |
| 4 | SportStock Gran Via | L'Hospitalet de Llobregat | Natación | NAT-0016 | Tapones de oído Ondia | 748 | 20 | 0.71 | 1047.20 |
| 5 | SportStock Terrassa | Terrassa | Ciclismo | CIC-0012 | Candado plegable Velox | 216 | 7 | 0.25 | 864.00 |
| 6 | SportStock Gran Via | L'Hospitalet de Llobregat | Ciclismo | CIC-0002 | Casco urbano Pedalix | 55 | 2 | 0.07 | 770.00 |
| 7 | SportStock Terrassa | Terrassa | Natación | NAT-0016 | Tapones de oído Ondia | 692 | 26 | 0.93 | 745.23 |
| 8 | SportStock Badalona | Badalona | Natación | NAT-0006 | Gorro textil Ondia | 542 | 23 | 0.82 | 659.83 |
| 9 | SportStock Gran Via | L'Hospitalet de Llobregat | Natación | NAT-0011 | Tubo frontal Aqualis | 185 | 8 | 0.29 | 647.50 |
| 10 | SportStock Gran Via | L'Hospitalet de Llobregat | Natación | NAT-0006 | Gorro textil Ondia | 662 | 30 | 1.07 | 617.87 |
| 11 | SportStock Badalona | Badalona | Natación | NAT-0007 | Tabla de natación Aqualis | 154 | 7 | 0.25 | 616.00 |
| 12 | SportStock Badalona | Badalona | Running | RUN-0025 | Bolsa de zapatillas Trailon | 174 | 8 | 0.29 | 609.00 |
| 13 | SportStock Badalona | Badalona | Deportes de raqueta | RAQ-0017 | Camiseta de tenis Raketa | 65 | 3 | 0.11 | 606.67 |
| 14 | SportStock Terrassa | Terrassa | Natación | NAT-0006 | Gorro textil Ondia | 472 | 22 | 0.79 | 600.73 |
| 15 | SportStock Terrassa | Terrassa | Natación | NAT-0011 | Tubo frontal Aqualis | 185 | 9 | 0.32 | 575.56 |

## Estado de stock a fecha de corte

> Qué mide: cuántas combinaciones producto-tienda están en rotura, bajo mínimo, sobrestock u OK el último día, en total y por categoría.
> Fórmula: Rotura = stock_final = 0; Bajo mínimo = 0 < stock_final < stock_minimo; Sobrestock = stock_final > stock_maximo; OK = el resto (stock_minimo <= stock_final <= stock_maximo).
> Por qué: los cuatro estados son excluyentes y cubren todas las referencias, así que sus porcentajes suman 100. Los umbrales salen de dim_producto (la ficha), no de un flag del hecho. El total dice el tamaño del problema; la categoría dice dónde mirar. TOTAL va al final para no romper el orden alfabético del desglose.

| categoria | referencias | rotura | bajo_minimo | sobrestock | ok | pct_rotura | pct_bajo_minimo | pct_sobrestock | pct_ok |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ciclismo | 125 | 8 | 12 | 8 | 97 | 6.40 | 9.60 | 6.40 | 77.60 |
| Deportes de equipo | 125 | 8 | 25 | 8 | 84 | 6.40 | 20.00 | 6.40 | 67.20 |
| Deportes de raqueta | 125 | 7 | 11 | 8 | 99 | 5.60 | 8.80 | 6.40 | 79.20 |
| Esquí | 125 | 15 | 28 | 9 | 73 | 12.00 | 22.40 | 7.20 | 58.40 |
| Fitness | 125 | 12 | 17 | 8 | 88 | 9.60 | 13.60 | 6.40 | 70.40 |
| Montaña | 125 | 10 | 50 | 4 | 61 | 8.00 | 40.00 | 3.20 | 48.80 |
| Natación | 125 | 13 | 6 | 8 | 98 | 10.40 | 4.80 | 6.40 | 78.40 |
| Running | 125 | 9 | 13 | 11 | 92 | 7.20 | 10.40 | 8.80 | 73.60 |
| TOTAL | 1000 | 82 | 162 | 64 | 692 | 8.20 | 16.20 | 6.40 | 69.20 |

## Días en rotura por categoría

> Qué mide: cuántos días estuvo en rotura una referencia media de la categoría, y qué porcentaje de los días-referencia del año acabó a cero.
> Fórmula: dias_referencia = filas de fact_stock de la categoría (producto-tienda-día); dias_referencia_en_rotura = las que tienen stock_final = 0; dias_rotura_medio = dias_referencia_en_rotura / referencias; pct_dias_referencia_rotura = dias_referencia_en_rotura / dias_referencia * 100.
> Por qué: "días en rotura" como suma de producto-tienda-día pasa de 365 y no se compara entre categorías de distinto tamaño. La media por referencia sí cabe en el año (0-365) y el porcentaje es el que pide el enunciado, sobre el universo de días-referencia y no sobre los días de calendario en los que alguna tienda se quedó a cero.

| categoria | referencias | dias_referencia_en_rotura | dias_referencia | dias_rotura_medio | pct_dias_referencia_rotura | peso_rotura_pct |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fitness | 125 | 4860 | 45625 | 38.88 | 10.65 | 15.71 |
| Running | 125 | 4815 | 45625 | 38.52 | 10.55 | 15.56 |
| Natación | 125 | 4505 | 45625 | 36.04 | 9.87 | 14.56 |
| Esquí | 125 | 3816 | 45625 | 30.53 | 8.36 | 12.33 |
| Deportes de equipo | 125 | 3339 | 45625 | 26.71 | 7.32 | 10.79 |
| Ciclismo | 125 | 3328 | 45625 | 26.62 | 7.29 | 10.76 |
| Deportes de raqueta | 125 | 3160 | 45625 | 25.28 | 6.93 | 10.21 |
| Montaña | 125 | 3118 | 45625 | 24.94 | 6.83 | 10.08 |

## Top 3 productos por categoría

> Qué mide: los tres productos de mayor importe dentro de cada categoría.
> Fórmula: ROW_NUMBER() OVER (PARTITION BY categoria ORDER BY importe DESC, sku). El sku desempató para que el puesto no dependa del orden de inserción.
> Por qué: el ranking por categoría evita que una categoría cara (esquí) ocupe todo el top global y deje sin voz al resto. Se ordena la salida por el importe de la categoría, no por el nombre, para que lo que más vende quede arriba si el informe corta filas.

| categoria | puesto | sku | nombre | marca | importe | unidades | margen_pct | importe_categoria |
| --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| Montaña | 1 | MON-0014 | Tienda de campaña Montix 2 plazas | Montix | 236427.57 | 1537 | 26.21 | 2379821.13 |
| Montaña | 2 | MON-0007 | Pantalón desmontable Montix | Montix | 172636.16 | 3485 | 20.46 | 2379821.13 |
| Montaña | 3 | MON-0023 | Piolet básico Montix | Montix | 156721.18 | 2130 | 30.18 | 2379821.13 |
| Esquí | 1 | ESQ-0002 | Esquí todoterreno Albor | Albor | 232335.29 | 619 | 31.45 | 1998246.74 |
| Esquí | 2 | ESQ-0005 | Bota de esquí alpino Nivex | Nivex | 196312.59 | 967 | 28.29 | 1998246.74 |
| Esquí | 3 | ESQ-0009 | Chaqueta de esquí Nivex | Nivex | 153210.38 | 993 | 24.51 | 1998246.74 |
| Running | 1 | RUN-0002 | Zapatilla trail Trailon X3 | Trailon | 185828.13 | 1676 | 33.02 | 1903396.54 |
| Running | 2 | RUN-0003 | Zapatilla asfalto Trailon Pace | Trailon | 163035.41 | 1742 | 26.56 | 1903396.54 |
| Running | 3 | RUN-0015 | Reloj GPS running Trailon | Trailon | 162074.13 | 1265 | 30.39 | 1903396.54 |
| Ciclismo | 1 | CIC-0018 | Pedales automáticos Pedalix | Pedalix | 181754.45 | 3078 | 21.27 | 1851047.99 |
| Ciclismo | 2 | CIC-0017 | Sillín deportivo Velox | Velox | 154368.46 | 3352 | 23.28 | 1851047.99 |
| Ciclismo | 3 | CIC-0021 | Chaqueta cortavientos Velox | Velox | 130813.68 | 2451 | 19.53 | 1851047.99 |
| Fitness | 1 | FIT-0004 | Barra olímpica Fitcore 20 kg | Fitcore | 151543.08 | 1367 | 27.57 | 1831188.94 |
| Fitness | 2 | FIT-0012 | Banco ajustable Fitcore | Fitcore | 148421.89 | 1250 | 24.73 | 1831188.94 |
| Fitness | 3 | FIT-0007 | Pesa rusa Fitcore 16 kg | Fitcore | 144848.90 | 3206 | 23.88 | 1831188.94 |
| Deportes de raqueta | 1 | RAQ-0004 | Raqueta de pádel Gripio Power | Gripio | 192597.45 | 1553 | 26.32 | 1779257.17 |
| Deportes de raqueta | 2 | RAQ-0015 | Zapatilla de pádel Raketa | Raketa | 167807.50 | 2453 | 23.75 | 1779257.17 |
| Deportes de raqueta | 3 | RAQ-0016 | Zapatilla de tenis Gripio | Gripio | 147707.61 | 2159 | 22.75 | 1779257.17 |
| Deportes de equipo | 1 | EQU-0018 | Escalera de agilidad Balonix | Balonix | 106195.60 | 5074 | 29.81 | 1363582.36 |
| Deportes de equipo | 2 | EQU-0016 | Marcador portátil Balonix | Balonix | 92936.91 | 2815 | 25.85 | 1363582.36 |

_4 filas más no mostradas (límite de presentación: 20)._

## Ventas mensuales y variación

> Qué mide: importe y unidades de cada mes, y la variación % frente al mes anterior.
> Fórmula: var_pct_importe = (importe - LAG(importe) OVER (ORDER BY mes)) / LAG(importe) * 100. Igual para unidades.
> Por qué: el mes se toma de dim_calendario, no de un substr de la fecha, para que el nombre del mes salga de la dimensión. Enero no tiene mes anterior dentro del extracto: la variación queda nula, no cero. La de unidades acompaña a la de importe para separar un movimiento de precio (rebajas, Black Friday) de uno de volumen.

| mes | nombre_mes | importe | unidades | var_pct_importe | var_pct_unidades |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | enero | 1367969.34 | 60600 | n/d | n/d |
| 2 | febrero | 1136638.47 | 38089 | -16.91 | -37.15 |
| 3 | marzo | 1251697.37 | 45446 | 10.12 | 19.32 |
| 4 | abril | 1155205.86 | 44884 | -7.71 | -1.24 |
| 5 | mayo | 1190534.94 | 48327 | 3.06 | 7.67 |
| 6 | junio | 1099736.27 | 46214 | -7.63 | -4.37 |
| 7 | julio | 1074481.30 | 66171 | -2.30 | 43.18 |
| 8 | agosto | 1039387.39 | 44367 | -3.27 | -32.95 |
| 9 | septiembre | 1190298.71 | 47489 | 14.52 | 7.04 |
| 10 | octubre | 1172074.13 | 43977 | -1.53 | -7.40 |
| 11 | noviembre | 1205039.02 | 45834 | 2.81 | 4.22 |
| 12 | diciembre | 1429675.35 | 46125 | 18.64 | 0.63 |
