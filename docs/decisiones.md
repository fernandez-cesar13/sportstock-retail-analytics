# Decisiones

Registro breve de lo que se eligió y de lo que se dejó fuera. Datos 100% sintéticos de la cadena ficticia SportStock. No describen a ninguna enseña real.

## Datos sintéticos, semilla fija y casos provocados

- **Decisión:** generar el universo con semilla fija (`numpy.random.default_rng`, defecto 42) y forzar rotura y sobrestock, no esperar a que salgan solos.
- **Alternativa descartada:** datos de una enseña real, o una semilla distinta en cada ejecución, o dejar que la rotura aparezca solo si la simulación casualmente llega a cero.
- **Motivo:** es un portfolio y tiene que poder defenderse. La misma semilla produce los mismos CSV. Los casos de alerta no salen de la semilla: son índices fijos, para poder señalarlos. 20 productos (el primero y el del medio de cada categoría de 25, más uno en Running, Fitness, Natación y Esquí) por 5 tiendas = 100 combinaciones, el 10% de 1.000. El sobrestock es otro 10%, tomado de las combinaciones sanas (una de cada nueve) y disjunto de la rotura. En rotura la ficha queda en mínimo 2 y máximo 5, y el plazo real suma 14 días al de la ficha. El sobrestock arranca con un pedido ya cursado de `2 * stock_maximo + 1` y, si vuelve a pedir, multiplica por 3. Reglas en [`generate_data.py`](../src/generate_data.py).

## Agregado diario en ventas

- **Decisión:** una fila por fecha, tienda y producto con unidades > 0. 224.317 filas en [ventas.csv](../data/raw/ventas.csv).
- **Alternativa descartada:** el ticket, o una línea por unidad.
- **Motivo:** el grano pedido es el día, y es el que cuadra con las salidas de stock. No hay tickets. `venta_id` es la clave técnica; la de negocio es el único `(fecha, tienda_id, producto_id)` de [`schema.sql`](../sql/schema.sql).

## Venta perdida = min(demanda, stock)

- **Decisión:** la venta del día es el mínimo entre la demanda y el stock tras las entradas. Lo que no hay, se pierde.
- **Alternativa descartada:** pedido pendiente del cliente (backorder) que se sirve cuando llega la reposición.
- **Motivo:** lo que no está en estantería no se vende. No hay stock negativo por construcción. La demanda es una Poisson de factores (producto, tienda, mes, día de la semana y eventos); la venta es la parte que cupo. Así `Unidades Vendidas` no es la demanda, y la rotura se ve en el stock, no en un pedido diferido.

## Política mínimo-máximo con plazo de entrega

- **Decisión:** si la posición (stock en tienda + pedidos que aún no han llegado) cae por debajo del mínimo, se pide hasta el máximo. El pedido llega al cabo de `lead_time_real` días.
- **Alternativa descartada:** reponer al día siguiente sin plazo, o un punto de pedido sin tope máximo.
- **Motivo:** el plazo es lo que separa el pedido de la estantería. En la ficha va de 2 a 21 días. El mínimo cubre el peor día recurrente (sábado de pico, tienda más grande) por ese plazo, no el pico de un día de Black Friday. En las combinaciones de rotura el plazo de la ficha parece razonable (mínimo 7) y el retraso del proveedor solo existe en la simulación: es lo que el maestro no cuenta y las alertas sí delatan.

## SQLite para la capa SQL

- **Decisión:** una base SQLite en `data/retail_stock.db`, creada con [`schema.sql`](../sql/schema.sql) y cargada con [`load.py`](../sql/load.py) usando `sqlite3` de la librería estándar.
- **Alternativa descartada:** SQLAlchemy, o un motor cliente-servidor.
- **Motivo:** `to_sql` acepta un `sqlite3.Connection` y el proyecto no depende de otro paquete. Las claves foráneas se encienden en la conexión (SQLite no las activa solo), las dimensiones entran antes que los hechos, y el esquema es el mismo estrella que el modelo. Basta para los KPI.

## PBIP + TMDL en vez de .pbix

- **Decisión:** proyecto [`RetailStock.pbip`](../powerbi/RetailStock.pbip) con el modelo en TMDL, bajo `powerbi/RetailStock.SemanticModel/definition/`.
- **Alternativa descartada:** un `.pbix` binario.
- **Motivo:** el TMDL es texto. Se lee, se compara y se versiona en Git. Un `.pbix` no deja ver la medida ni la relación sin abrir Desktop.

## Informe PBIR vacío generado por Desktop

- **Decisión:** dejar el informe como el caparazón PBIR que genera Desktop: solo [`definition.pbir`](../powerbi/RetailStock.Report/definition.pbir), con la referencia al modelo semántico. Sin páginas.
- **Alternativa descartada:** escribir a mano el JSON de las páginas, o dar por cerrado el informe en este paso.
- **Motivo:** las páginas las construye Cesar en Desktop sobre un modelo ya cerrado. El PBIR vacío apunta al modelo (`datasetReference.byPath`) y no mezcla visuales a medio hacer con las medidas.

## Cultura en-US en Power Query por el punto decimal

- **Decisión:** `Table.TransformColumnTypes` con cultura `"en-US"` en las seis particiones. La cultura del modelo sigue siendo `es-ES` ([`model.tmdl`](../powerbi/RetailStock.SemanticModel/definition/model.tmdl)).
- **Alternativa descartada:** tipar las columnas con la cultura del modelo (`es-ES`).
- **Motivo:** el CSV usa punto decimal y fechas ISO. Con `es-ES` el punto es separador de miles y el importe se lee mal. `en-US` solo entra en el paso de tipos; el informe sigue en español.

## Parámetro RutaDatos

- **Decisión:** una consulta de parámetro, obligatoria, con la carpeta de los CSV. Cada partición concatena `RutaDatos` y el nombre del archivo.
- **Alternativa descartada:** la ruta absoluta escrita en cada tabla.
- **Motivo:** clonar el repo a otra carpeta no obliga a tocar seis particiones. Se cambia el parámetro una vez. Tiene que terminar en `\`. Cómo: [configurar_ruta_datos.md](configurar_ruta_datos.md).

## Copo de nieve DimProducto → DimCategoria

- **Decisión:** categoría y sección en `DimCategoria` (8 filas). El producto guarda `categoria_id` y la relación es `DimProducto_DimCategoria`. Los hechos no apuntan a la categoría.
- **Alternativa descartada:** desnormalizar categoría y sección dentro de `DimProducto` (estrella pura), o relacionar los hechos directamente con la categoría.
- **Motivo:** la sección es un atributo de la categoría, no del producto. Un salto evita repetirla en 200 fichas y deja filtrar la venta y el stock por sección sin una segunda relación desde los hechos. No es un copo profundo: un solo nivel. El mismo FK está en [`schema.sql`](../sql/schema.sql).

## CSV en el repo (~17,6 MB)

- **Decisión:** versionar los seis CSV de `data/raw/`.
- **Alternativa descartada:** no subir los datos y regenerarlos siempre, o guardarlos en un binario.
- **Motivo:** pesan 17.584.684 bytes, unos 17,6 MB. Caben en el repo. Quien abre el `.pbip` o carga SQLite no tiene que ejecutar el generador. Van en UTF-8, separador coma, fechas ISO e importes a céntimos.

## OpenCode como asistente, código revisado a mano

- **Decisión:** usar OpenCode para generar código, y dejar en el repo solo lo revisado a mano.
- **Alternativa descartada:** aceptar el generado sin leerlo, o escribir cada archivo sin asistente.
- **Motivo:** el asistente acelera el andamiaje; la defensa en la entrevista no. Las reglas que importan están escritas en el fuente (semilla, venta perdida, mínimo-máximo, grano, cultura `en-US`, `LASTDATE`) para poder explicarlas sin recurrir al chat. Lo que no se sostiene, no se versiona.
