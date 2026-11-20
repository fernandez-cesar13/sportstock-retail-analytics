-- Modelo en estrella de SportStock (datos sintéticos, año 2025).
--
-- Dimensiones: categoría, producto, tienda y calendario.
-- Hechos: ventas (grano fecha-tienda-producto con unidades > 0) y stock
-- diario (el mismo grano, todos los días, haya venta o no).
--
-- La fecha del calendario es TEXT ISO (YYYY-MM-DD) y es la PK. Ordena
-- cronológicamente sin un sustituto entero, y es la misma clave que ya
-- traen los hechos: un id de fecha solo añadiría un join.
--
-- Reejecutable: se tiran primero los hechos. Con PRAGMA foreign_keys = ON
-- no se puede borrar una dimensión mientras un hecho la referencia.
-- La clave foránea no se activa sola en SQLite: load.py la enciende en
-- la conexión, y este PRAGMA cubre quien ejecute el script a mano.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fact_ventas;
DROP TABLE IF EXISTS fact_stock;
DROP TABLE IF EXISTS dim_producto;
DROP TABLE IF EXISTS dim_categoria;
DROP TABLE IF EXISTS dim_tienda;
DROP TABLE IF EXISTS dim_calendario;

CREATE TABLE dim_categoria (
    categoria_id INTEGER PRIMARY KEY,
    categoria    TEXT NOT NULL,
    seccion      TEXT NOT NULL
);

CREATE TABLE dim_producto (
    producto_id    INTEGER PRIMARY KEY,
    sku            TEXT    NOT NULL UNIQUE,
    nombre         TEXT    NOT NULL,
    categoria_id   INTEGER NOT NULL,
    marca          TEXT    NOT NULL,
    precio_coste   REAL    NOT NULL,
    precio_venta   REAL    NOT NULL,
    stock_minimo   INTEGER NOT NULL,
    stock_maximo   INTEGER NOT NULL,
    lead_time_dias INTEGER NOT NULL,
    -- El markup de ficha es sobre coste; el CHECK solo exige que la venta
    -- supere al coste. El margen % de los KPI se calcula sobre la venta.
    CONSTRAINT ck_producto_precio CHECK (precio_venta > precio_coste),
    CONSTRAINT ck_producto_coste CHECK (precio_coste > 0),
    CONSTRAINT ck_producto_stock CHECK (stock_maximo > stock_minimo),
    CONSTRAINT ck_producto_minimo CHECK (stock_minimo >= 0),
    CONSTRAINT ck_producto_plazo CHECK (lead_time_dias > 0),
    CONSTRAINT fk_producto_categoria
        FOREIGN KEY (categoria_id) REFERENCES dim_categoria (categoria_id)
);

CREATE TABLE dim_tienda (
    tienda_id INTEGER PRIMARY KEY,
    nombre    TEXT    NOT NULL,
    ciudad    TEXT    NOT NULL,
    tipo      TEXT    NOT NULL,
    m2        INTEGER NOT NULL,
    CONSTRAINT ck_tienda_m2 CHECK (m2 > 0),
    CONSTRAINT ck_tienda_tipo CHECK (tipo IN ('grande', 'ciudad'))
);

CREATE TABLE dim_calendario (
    fecha            TEXT PRIMARY KEY,
    "año"            INTEGER NOT NULL,
    mes              INTEGER NOT NULL,
    nombre_mes       TEXT    NOT NULL,
    semana           INTEGER NOT NULL,
    dia_semana       TEXT    NOT NULL,
    -- SQLite no tiene booleano: 0/1. load.py convierte True/False del CSV.
    es_fin_de_semana INTEGER NOT NULL,
    temporada        TEXT    NOT NULL,
    es_rebajas       INTEGER NOT NULL,
    es_black_friday  INTEGER NOT NULL,
    CONSTRAINT ck_calendario_fecha CHECK (
        fecha GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
    ),
    CONSTRAINT ck_calendario_mes CHECK (mes BETWEEN 1 AND 12),
    CONSTRAINT ck_calendario_semana CHECK (semana BETWEEN 1 AND 53),
    CONSTRAINT ck_calendario_finde CHECK (es_fin_de_semana IN (0, 1)),
    CONSTRAINT ck_calendario_rebajas CHECK (es_rebajas IN (0, 1)),
    CONSTRAINT ck_calendario_bf CHECK (es_black_friday IN (0, 1))
);

CREATE TABLE fact_ventas (
    venta_id    INTEGER PRIMARY KEY,
    fecha       TEXT    NOT NULL,
    tienda_id   INTEGER NOT NULL,
    producto_id INTEGER NOT NULL,
    unidades    INTEGER NOT NULL,
    importe     REAL    NOT NULL,
    coste       REAL    NOT NULL,
    -- El grano pedido es el agregado diario, no el ticket. venta_id es
    -- la PK técnica; la de negocio es fecha + tienda + producto.
    CONSTRAINT uq_ventas_grano UNIQUE (fecha, tienda_id, producto_id),
    CONSTRAINT ck_ventas_unidades CHECK (unidades > 0),
    CONSTRAINT ck_ventas_importe CHECK (importe >= 0),
    CONSTRAINT ck_ventas_coste CHECK (coste >= 0),
    CONSTRAINT fk_ventas_fecha
        FOREIGN KEY (fecha) REFERENCES dim_calendario (fecha),
    CONSTRAINT fk_ventas_tienda
        FOREIGN KEY (tienda_id) REFERENCES dim_tienda (tienda_id),
    CONSTRAINT fk_ventas_producto
        FOREIGN KEY (producto_id) REFERENCES dim_producto (producto_id)
);

CREATE TABLE fact_stock (
    fecha       TEXT    NOT NULL,
    tienda_id   INTEGER NOT NULL,
    producto_id INTEGER NOT NULL,
    stock_final INTEGER NOT NULL,
    entradas    INTEGER NOT NULL,
    salidas     INTEGER NOT NULL,
    CONSTRAINT pk_stock PRIMARY KEY (fecha, tienda_id, producto_id),
    CONSTRAINT ck_stock_final CHECK (stock_final >= 0),
    CONSTRAINT ck_stock_entradas CHECK (entradas >= 0),
    CONSTRAINT ck_stock_salidas CHECK (salidas >= 0),
    CONSTRAINT fk_stock_fecha
        FOREIGN KEY (fecha) REFERENCES dim_calendario (fecha),
    CONSTRAINT fk_stock_tienda
        FOREIGN KEY (tienda_id) REFERENCES dim_tienda (tienda_id),
    CONSTRAINT fk_stock_producto
        FOREIGN KEY (producto_id) REFERENCES dim_producto (producto_id)
);

-- Índices de las FK de los hechos. La PK compuesta y el UNIQUE ya indexan
-- (fecha, tienda_id, producto_id), así que fecha queda cubierta como
-- primera columna; tienda_id y producto_id no, y son las que usan los
-- joins del KPI cuando no se filtra por fecha. Se indexan las tres para
-- que cada FK tenga un índice propio y el plan no dependa del orden de
-- la clave compuesta.
CREATE INDEX idx_fact_ventas_fecha ON fact_ventas (fecha);
CREATE INDEX idx_fact_ventas_tienda_id ON fact_ventas (tienda_id);
CREATE INDEX idx_fact_ventas_producto_id ON fact_ventas (producto_id);
CREATE INDEX idx_fact_stock_fecha ON fact_stock (fecha);
CREATE INDEX idx_fact_stock_tienda_id ON fact_stock (tienda_id);
CREATE INDEX idx_fact_stock_producto_id ON fact_stock (producto_id);
