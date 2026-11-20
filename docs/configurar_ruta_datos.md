# Configurar la ruta de los datos

El modelo semántico no lleva la carpeta de los CSV escrita en cada tabla. La lee del parámetro **RutaDatos**: una consulta de parámetro de tipo texto, obligatoria, definida en `powerbi/RetailStock.SemanticModel/definition/expressions.tmdl`. Cada partición concatena ese valor con el nombre del archivo (`RutaDatos & "ventas.csv"`, etc.).

Valor por defecto en este equipo:

`C:\Users\morde\Documents\Proyectos\retail-stock-analytics\data\raw\`

La ruta tiene que terminar en barra invertida (`\`). Si falta, el nombre del CSV se pega al de la carpeta y la lectura falla.

## Cómo cambiarla

En Power BI Desktop: **Transformar datos** > **Administrar parámetros** > **RutaDatos**. Escribe la carpeta de los CSV, terminada en `\`.

También se puede editar el literal de `expression RutaDatos` en `expressions.tmdl`.

Tras cambiarlo hay que pulsar **Actualizar** para volver a leer los CSV.

## Características en versión preliminar

Al abrir el `.pbip`, Desktop puede pedir activar las características en versión preliminar de PBIP/TMDL: **Archivo** > **Opciones** > **Características en versión preliminar**.
