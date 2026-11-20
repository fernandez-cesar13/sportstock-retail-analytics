"""Generador de datos sintéticos de stock para la cadena ficticia SportStock.

Todo el universo es inventado: no hay tiendas, marcas ni cifras de Decathlon ni
de ninguna enseña real. Sirve para un portfolio de Data & BI y tiene que poder
defenderse en una entrevista, así que cada regla de negocio está comentada.

Modelo, en una frase: la demanda diaria es una Poisson de factores (producto,
tienda, mes, día de la semana y eventos); la venta real es el mínimo entre esa
demanda y el stock disponible; el stock se repone con una política mínimo-máximo
y un plazo de entrega. Lo que no hay en estantería es venta perdida, no pedido
pendiente del cliente.

Contrato público para los tests:
- ``generar_datos(seed)`` devuelve los seis DataFrames y no escribe a disco.
- ``guardar_csv(tablas, output_dir)`` persiste esos DataFrames.
La semilla entra solo por ``numpy.random.default_rng``. Mismo seed, mismos
datos. El orden de las extracciones forma parte de ese contrato: no intercales
otras llamadas al generador.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# Raíz del proyecto calculada desde este archivo (src/generate_data.py), no
# desde el directorio de trabajo. Así `python src\generate_data.py` funciona
# se lance desde donde se lance.
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

ANIO = 2025
N_PRODUCTOS_POR_CATEGORIA = 25
N_TIENDAS = 5

# Umbral de superficie para clasificar la tienda. Las dos por encima de 2000 m2
# son el buque insignia (Diagonal) y la grande de Sabadell; el resto son tienda
# de ciudad. El factor de demanda no se guarda en el CSV (no está en el contrato):
# se deriva de los m2 respecto a la media, así la tienda media tiene factor 1
# y la demanda base del producto se lee en esas unidades.
UMBRAL_M2_GRANDE = 2000

# Día laborable normal = 1.0. El sábado ~1.6x y el domingo ~1.3x respecto a ese
# día, como pide el diseño. Índice 0 = lunes, alineado con pandas.day_of_week.
#
# Decisión: las tiendas ABREN el domingo. En el retail deportivo del área de
# Barcelona el domingo es día comercial, con menos tráfico que el sábado. Cerrar
# el domingo pondría esas ventas a cero y falsearía el stock (un día sin salidas
# que parece baja rotación y no lo es).
FACTOR_DIA_SEMANA = np.array([1.00, 0.95, 1.00, 1.05, 1.15, 1.60, 1.30], dtype=np.float64)

# Eventos de cadena (mismo factor y mismo descuento en todas las tiendas y
# productos: son campañas de central, no promociones locales).
# El día de Black Friday sustituye al factor de la semana (3.0, no 1.8 * 3):
# el enunciado habla de un pico ~3x, no de un pico encima de la semana.
FACTOR_REBAJAS = 1.5
DESCUENTO_REBAJAS = 0.30
FACTOR_SEMANA_BLACK_FRIDAY = 1.8
FACTOR_BLACK_FRIDAY = 3.0
DESCUENTO_BLACK_FRIDAY = 0.25
FACTOR_NAVIDAD = 1.3

# Casos de alerta del dashboard. Son deterministas (no salen de la semilla) para
# poder señalarlos en una entrevista: "estos productos están rotos a propósito".
# 20 productos x 5 tiendas = 100 combinaciones = 10% de 1000.
# El sobrestock es el otro 10%, tomado de los productos sanos.
RETRASO_PROVEEDOR_DIAS = 14
MULTIPLICADOR_SOBRESTOCK = 3
BASE_MINIMA_ROTURA = 1.0
STOCK_MINIMO_ROTURA = 2
STOCK_MAXIMO_ROTURA = 5

TABLAS = (
    "categorias",
    "productos",
    "tiendas",
    "calendario",
    "ventas",
    "stock_diario",
)

NOMBRES_MES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
NOMBRES_DIA = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)
# Estaciones meteorológicas (dic-feb, mar-may, jun-ago, sep-nov), no las
# astronómicas. Así "Invierno" en el calendario coincide con el pico de esquí
# y de montaña, que también está definido por meses enteros.
TEMPORADA_POR_MES = (
    "Invierno",
    "Invierno",
    "Primavera",
    "Primavera",
    "Primavera",
    "Verano",
    "Verano",
    "Verano",
    "Otoño",
    "Otoño",
    "Otoño",
    "Invierno",
)

# Factores estacionales por categoría y mes (columna 0 = enero ... 11 = diciembre).
# 1.0 sería un mes neutro. No copian una serie real: están elegidos para que el
# dashboard muestre una estacionalidad que se pueda contar.
#
# - Running y Ciclismo: pico de marzo a junio (buen tiempo, carreras, salidas).
# - Fitness: pico en enero (propósitos de año nuevo) y septiembre (vuelta a la rutina).
# - Montaña: pico de invierno (diciembre-febrero) y un repunte en otoño.
# - Natación: pico de verano (junio-agosto); el resto es residual de club cubierto.
# - Deportes de equipo: pico en septiembre-octubre (vuelta al cole y temporada).
# - Esquí: pico de invierno (diciembre-febrero); en verano la demanda es testimonial.
# - Deportes de raqueta: pico de primavera-verano (club de tenis y pádel al aire
#   libre). No venía impuesto; se documenta para que la serie no sea plana.
CATEGORIAS = (
    {
        "categoria_id": 1,
        "categoria": "Running",
        "seccion": "Deportes de resistencia",
        "prefijo_sku": "RUN",
        "factores": (0.75, 0.85, 1.35, 1.55, 1.50, 1.30, 0.95, 0.85, 1.05, 0.95, 0.80, 0.65),
    },
    {
        "categoria_id": 2,
        "categoria": "Fitness",
        "seccion": "Deportes de interior",
        "prefijo_sku": "FIT",
        "factores": (1.70, 1.20, 1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 1.45, 1.10, 0.95, 0.85),
    },
    {
        "categoria_id": 3,
        "categoria": "Ciclismo",
        "seccion": "Deportes de resistencia",
        "prefijo_sku": "CIC",
        "factores": (0.55, 0.70, 1.40, 1.60, 1.55, 1.35, 1.10, 0.95, 1.00, 0.80, 0.55, 0.45),
    },
    {
        "categoria_id": 4,
        "categoria": "Montaña",
        "seccion": "Outdoor",
        "prefijo_sku": "MON",
        "factores": (1.45, 1.35, 0.90, 0.75, 0.70, 0.65, 0.70, 0.80, 1.15, 1.30, 1.20, 1.50),
    },
    {
        "categoria_id": 5,
        "categoria": "Deportes de raqueta",
        "seccion": "Deportes de interior",
        "prefijo_sku": "RAQ",
        "factores": (0.70, 0.75, 0.95, 1.20, 1.35, 1.40, 1.30, 1.15, 0.95, 0.85, 0.75, 0.65),
    },
    {
        "categoria_id": 6,
        "categoria": "Natación",
        "seccion": "Agua",
        "prefijo_sku": "NAT",
        "factores": (0.40, 0.45, 0.55, 0.75, 1.05, 1.55, 1.70, 1.60, 0.90, 0.55, 0.40, 0.35),
    },
    {
        "categoria_id": 7,
        "categoria": "Deportes de equipo",
        # No encaja en indoor ni en outdoor (un balón de fútbol y uno de
        # baloncesto no comparten sección física). Se agrupa aparte.
        "seccion": "Deportes colectivos",
        "prefijo_sku": "EQU",
        "factores": (0.70, 0.75, 0.85, 0.90, 0.85, 0.70, 0.60, 0.80, 1.65, 1.55, 1.05, 0.85),
    },
    {
        "categoria_id": 8,
        "categoria": "Esquí",
        "seccion": "Nieve",
        "prefijo_sku": "ESQ",
        "factores": (1.80, 1.65, 0.85, 0.35, 0.18, 0.12, 0.10, 0.12, 0.28, 0.60, 1.15, 1.75),
    },
)

TIENDAS = (
    {"nombre": "SportStock Diagonal", "ciudad": "Barcelona", "m2": 3400},
    {"nombre": "SportStock Gran Via", "ciudad": "L'Hospitalet de Llobregat", "m2": 1150},
    {"nombre": "SportStock Badalona", "ciudad": "Badalona", "m2": 980},
    {"nombre": "SportStock Sabadell", "ciudad": "Sabadell", "m2": 2700},
    {"nombre": "SportStock Terrassa", "ciudad": "Terrassa", "m2": 1250},
)

# (nombre, marca, coste_base_eur). El coste base es coherente con el tipo de
# artículo; luego se le aplica un ruido pequeño de semilla para que dos seeds
# no compartan precios, sin que un calcetín salga más caro que un esquí.
# Marcas inventadas: Trailon, Corrid, Fitcore, Pulso, Velox, Pedalix, Montix,
# Cimera, Raketa, Gripio, Aqualis, Ondia, Ludix, Balonix, Nivex, Albor.
CATALOGO: dict[str, tuple[tuple[str, str, float], ...]] = {
    "Running": (
        ("Zapatilla trail Trailon X1", "Trailon", 55),
        ("Zapatilla trail Trailon X3", "Trailon", 75),
        ("Zapatilla asfalto Trailon Pace", "Trailon", 65),
        ("Zapatilla mixta Corrid Road", "Corrid", 50),
        ("Camiseta técnica running Trailon", "Trailon", 18),
        ("Camiseta manga larga Corrid", "Corrid", 22),
        ("Mallas running Trailon Elite", "Trailon", 28),
        ("Pantalón corto running Corrid", "Corrid", 16),
        ("Cortavientos Trailon", "Trailon", 35),
        ("Chaqueta impermeable Trailon", "Trailon", 60),
        ("Calcetín técnico Trailon pack 3", "Trailon", 8),
        ("Gorra running Trailon", "Trailon", 12),
        ("Mochila de hidratación Trailon 5 L", "Trailon", 32),
        ("Cinturón porta-dorsal Corrid", "Corrid", 14),
        ("Reloj GPS running Trailon", "Trailon", 90),
        ("Luz frontal running Corrid", "Corrid", 15),
        ("Botella blanda Trailon 500 ml", "Trailon", 10),
        ("Guantes running Corrid", "Corrid", 12),
        ("Braga de cuello Trailon", "Trailon", 9),
        ("Plantillas running Trailon", "Trailon", 14),
        ("Rodilleras running Corrid", "Corrid", 16),
        ("Chaleco reflectante Trailon", "Trailon", 18),
        ("Gafas running Trailon", "Trailon", 20),
        ("Cinta de sudor Corrid", "Corrid", 6),
        ("Bolsa de zapatillas Trailon", "Trailon", 12),
    ),
    "Fitness": (
        ("Mancuerna hexagonal Fitcore 5 kg", "Fitcore", 12),
        ("Mancuerna hexagonal Fitcore 10 kg", "Fitcore", 20),
        ("Mancuerna hexagonal Fitcore 15 kg", "Fitcore", 28),
        ("Barra olímpica Fitcore 20 kg", "Fitcore", 85),
        ("Disco olímpico Fitcore 10 kg", "Fitcore", 22),
        ("Pesa rusa Fitcore 8 kg", "Fitcore", 18),
        ("Pesa rusa Fitcore 16 kg", "Fitcore", 32),
        ("Esterilla fitness Pulso 8 mm", "Pulso", 14),
        ("Comba de velocidad Pulso", "Pulso", 8),
        ("Banda elástica Fitcore media", "Fitcore", 6),
        ("Set de bandas elásticas Pulso", "Pulso", 12),
        ("Banco ajustable Fitcore", "Fitcore", 95),
        ("Barra de dominadas Pulso", "Pulso", 25),
        ("Rueda abdominal Fitcore", "Fitcore", 10),
        ("Step aeróbic Pulso 15 cm", "Pulso", 28),
        ("Pelota de pilates Fitcore 65 cm", "Fitcore", 12),
        ("Rodillo de espuma Pulso", "Pulso", 14),
        ("Guantes de entrenamiento Fitcore", "Fitcore", 10),
        ("Cinturón lumbar Fitcore", "Fitcore", 18),
        ("Toalla de microfibra Pulso", "Pulso", 8),
        ("Botella shaker Fitcore 700 ml", "Fitcore", 6),
        ("Lastre para tobillos Pulso 2 kg", "Pulso", 12),
        ("Cintas de suspensión Fitcore", "Fitcore", 22),
        ("Colchoneta plegable Pulso", "Pulso", 20),
        ("Pulsómetro fitness Fitcore", "Fitcore", 35),
    ),
    "Ciclismo": (
        ("Casco de ciclismo Velox", "Velox", 55),
        ("Casco urbano Pedalix", "Pedalix", 35),
        ("Maillot de ciclismo Velox", "Velox", 40),
        ("Culote con tirantes Velox", "Velox", 45),
        ("Guantes de ciclismo Pedalix", "Pedalix", 15),
        ("Calcetines de ciclismo Velox", "Velox", 8),
        ("Gafas de ciclismo Velox", "Velox", 25),
        ("Bidón de ciclismo Velox 750 ml", "Velox", 6),
        ("Portabidón Pedalix", "Pedalix", 8),
        ("Luz delantera Velox", "Velox", 22),
        ("Luz trasera Pedalix", "Pedalix", 12),
        ("Candado plegable Velox", "Velox", 18),
        ("Bomba de mano Pedalix", "Pedalix", 12),
        ("Cámara de repuesto Velox 700", "Velox", 6),
        ("Kit de parches Pedalix", "Pedalix", 4),
        ("Cubierta de ciclismo Velox 28", "Velox", 22),
        ("Sillín deportivo Velox", "Velox", 35),
        ("Pedales automáticos Pedalix", "Pedalix", 48),
        ("Alforja trasera Velox 20 L", "Velox", 40),
        ("Soporte de móvil Pedalix", "Pedalix", 14),
        ("Chaqueta cortavientos Velox", "Velox", 45),
        ("Manguitos de ciclismo Pedalix", "Pedalix", 12),
        ("Calapiés Velox", "Velox", 8),
        ("Multiherramienta Pedalix", "Pedalix", 14),
        ("Portaequipajes Velox", "Velox", 28),
    ),
    "Montaña": (
        ("Bota de montaña Montix", "Montix", 85),
        ("Bota ligera Cimera", "Cimera", 60),
        ("Mochila de montaña Montix 30 L", "Montix", 55),
        ("Mochila de montaña Cimera 20 L", "Cimera", 38),
        ("Chaqueta softshell Montix", "Montix", 65),
        ("Forro polar Cimera", "Cimera", 28),
        ("Pantalón desmontable Montix", "Montix", 40),
        ("Bastón telescópico Montix par", "Montix", 30),
        ("Frontal LED Cimera 300", "Cimera", 22),
        ("Cantimplora Montix 1 L", "Montix", 10),
        ("Navaja multiusos Cimera", "Cimera", 16),
        ("Saco de dormir Montix 10C", "Montix", 45),
        ("Esterilla aislante Cimera", "Cimera", 25),
        ("Tienda de campaña Montix 2 plazas", "Montix", 120),
        ("Brújula Cimera", "Cimera", 12),
        ("Gafas de sol Montix", "Montix", 22),
        ("Guantes softshell Montix", "Montix", 18),
        ("Tubular de cuello Cimera", "Cimera", 8),
        ("Poncho impermeable Montix", "Montix", 14),
        ("Botiquín básico Cimera", "Cimera", 12),
        ("Linterna de mano Montix", "Montix", 15),
        ("Crampones ligeros Cimera", "Cimera", 40),
        ("Piolet básico Montix", "Montix", 55),
        ("Cuerda auxiliar Cimera 20 m", "Cimera", 35),
        ("Mosquetón de seguridad Montix", "Montix", 10),
    ),
    "Deportes de raqueta": (
        ("Raqueta de tenis Raketa Pro 300", "Raketa", 90),
        ("Raqueta de tenis Gripio Club", "Gripio", 45),
        ("Raqueta de pádel Raketa Control", "Raketa", 70),
        ("Raqueta de pádel Gripio Power", "Gripio", 85),
        ("Raqueta de bádminton Raketa", "Raketa", 30),
        ("Pelotas de tenis Raketa pack 3", "Raketa", 5),
        ("Pelotas de pádel Gripio pack 3", "Gripio", 5),
        ("Volantes de bádminton Raketa 6", "Raketa", 6),
        ("Overgrip Raketa pack 3", "Raketa", 4),
        ("Cordaje de tenis Gripio", "Gripio", 10),
        ("Bolsa raquetero Raketa", "Raketa", 35),
        ("Paletero de pádel Gripio", "Gripio", 40),
        ("Muñequera Raketa par", "Raketa", 6),
        ("Visera de pádel Gripio", "Gripio", 10),
        ("Zapatilla de pádel Raketa", "Raketa", 55),
        ("Zapatilla de tenis Gripio", "Gripio", 50),
        ("Camiseta de tenis Raketa", "Raketa", 18),
        ("Falda de pádel Gripio", "Gripio", 22),
        ("Red portátil de bádminton Raketa", "Raketa", 25),
        ("Toalla de pista Gripio", "Gripio", 8),
        ("Antivibrador Raketa pack", "Raketa", 4),
        ("Presurizador de pelotas Gripio", "Gripio", 12),
        ("Cinta protectora Raketa", "Raketa", 6),
        ("Gorra de tenis Gripio", "Gripio", 12),
        ("Botella de pista Raketa 750 ml", "Raketa", 8),
    ),
    "Natación": (
        ("Bañador jammer Aqualis", "Aqualis", 22),
        ("Bañador de mujer Aqualis", "Aqualis", 24),
        ("Gafas de natación Aqualis", "Aqualis", 12),
        ("Gafas de natación Ondia espejo", "Ondia", 16),
        ("Gorro de silicona Aqualis", "Aqualis", 6),
        ("Gorro textil Ondia", "Ondia", 5),
        ("Tabla de natación Aqualis", "Aqualis", 12),
        ("Pullboy de entreno Ondia", "Ondia", 10),
        ("Aletas cortas de entreno Aqualis", "Aqualis", 22),
        ("Aletas largas Ondia", "Ondia", 28),
        ("Tubo frontal Aqualis", "Aqualis", 14),
        ("Toalla de microfibra Ondia", "Ondia", 12),
        ("Chanclas de piscina Aqualis", "Aqualis", 8),
        ("Albornoz de piscina Ondia", "Ondia", 25),
        ("Pinza de nariz Aqualis", "Aqualis", 3),
        ("Tapones de oído Ondia", "Ondia", 4),
        ("Bolsa impermeable Aqualis", "Aqualis", 10),
        ("Cinturón de flotación Ondia", "Ondia", 12),
        ("Churro de piscina Aqualis", "Aqualis", 6),
        ("Cronómetro de natación Ondia", "Ondia", 15),
        ("Camiseta anti-UV Aqualis", "Aqualis", 18),
        ("Palo de acuagym Ondia", "Ondia", 8),
        ("Mancuernas acuáticas Aqualis", "Aqualis", 14),
        ("Escarpines Ondia", "Ondia", 10),
        ("Champú sin aclarado Aqualis", "Aqualis", 5),
    ),
    "Deportes de equipo": (
        ("Balón de fútbol Ludix", "Ludix", 18),
        ("Balón de fútbol sala Balonix", "Balonix", 16),
        ("Balón de baloncesto Ludix", "Ludix", 20),
        ("Balón de balonmano Balonix", "Balonix", 16),
        ("Balón de voleibol Ludix", "Ludix", 15),
        ("Conos de entrenamiento Ludix set 10", "Ludix", 12),
        ("Petos Ludix pack 6", "Ludix", 14),
        ("Silbato de árbitro Balonix", "Balonix", 5),
        ("Red de portería Ludix 3x2", "Ludix", 28),
        ("Bomba de balones Balonix", "Balonix", 8),
        ("Espinilleras Ludix", "Ludix", 10),
        ("Guantes de portero Balonix", "Balonix", 22),
        ("Rodilleras de voleibol Ludix", "Ludix", 12),
        ("Muñequeras de baloncesto Balonix", "Balonix", 6),
        ("Bolsa de balones Ludix", "Ludix", 18),
        ("Marcador portátil Balonix", "Balonix", 25),
        ("Valla de entrenamiento Ludix", "Ludix", 20),
        ("Escalera de agilidad Balonix", "Balonix", 14),
        ("Balón medicinal Ludix 4 kg", "Ludix", 22),
        ("Set de aros Ludix", "Ludix", 15),
        ("Brazalete de capitán Balonix", "Balonix", 4),
        ("Botella de equipo Ludix 1 L", "Ludix", 6),
        ("Mochila de equipo Balonix", "Balonix", 20),
        ("Silbato electrónico Ludix", "Ludix", 12),
        ("Pizarra táctica Balonix", "Balonix", 15),
    ),
    "Esquí": (
        ("Esquí alpino Nivex", "Nivex", 220),
        ("Esquí todoterreno Albor", "Albor", 260),
        ("Fijación alpina Nivex", "Nivex", 90),
        ("Bastón de esquí Nivex", "Nivex", 25),
        ("Bota de esquí alpino Nivex", "Nivex", 140),
        ("Casco de esquí Albor", "Albor", 55),
        ("Gafas de esquí Nivex", "Nivex", 45),
        ("Guantes de esquí Albor", "Albor", 30),
        ("Chaqueta de esquí Nivex", "Nivex", 120),
        ("Pantalón de esquí Albor", "Albor", 90),
        ("Camiseta térmica Nivex", "Nivex", 28),
        ("Calcetines de esquí Albor", "Albor", 12),
        ("Pasamontañas Nivex", "Nivex", 14),
        ("Mochila de esquí Albor 20 L", "Albor", 48),
        ("Funda de esquís Nivex", "Nivex", 25),
        ("Cera de deslizamiento Albor", "Albor", 8),
        ("Antivaho Nivex", "Nivex", 6),
        ("Protector de espalda Albor", "Albor", 55),
        ("Malla térmica Nivex", "Nivex", 32),
        ("Calentador de cuello Albor", "Albor", 12),
        ("Candado para esquís Nivex", "Nivex", 18),
        ("Toalla de nieve Albor", "Albor", 10),
        ("Botella isotérmica Nivex", "Nivex", 16),
        ("Cubrebotas de esquí Albor", "Albor", 20),
        ("Bolsa para botas Nivex", "Nivex", 22),
    ),
}


def redondear_euros(valores: np.ndarray) -> np.ndarray:
    """Redondea a céntimos evitando que el binario deje colas en el CSV."""
    centimos = np.rint(np.asarray(valores, dtype=np.float64) * 100.0).astype(np.int64)
    return centimos / 100.0


def factores_tienda() -> np.ndarray:
    """Factor comercial de cada tienda: m2 relativos a la media de la cadena."""
    metros = np.array([tienda["m2"] for tienda in TIENDAS], dtype=np.float64)
    return metros / metros.mean()


def indices_productos_rotura() -> np.ndarray:
    """Índices 0-based de los productos con ficha infradimensionada.

    Dentro de cada bloque de 25 se marcan el primero y el del medio. En las
    categorías con pico más brusco (Running, Fitness, Natación y Esquí) se
    marca uno más, para que las alertas se vean también en Black Friday,
    rebajas de enero y temporada alta. 8*2 + 4 = 20 productos, el 10%.
    """
    indices: list[int] = []
    for categoria in range(len(CATEGORIAS)):
        base = categoria * N_PRODUCTOS_POR_CATEGORIA
        indices.append(base + 0)
        indices.append(base + 12)
    for categoria in (0, 1, 5, 7):
        indices.append(categoria * N_PRODUCTOS_POR_CATEGORIA + 20)
    return np.array(sorted(set(indices)), dtype=np.int64)


def generar_categorias() -> pd.DataFrame:
    """Ocho categorías de la cadena, con la sección que las agrupa."""
    return pd.DataFrame(
        {
            "categoria_id": [c["categoria_id"] for c in CATEGORIAS],
            "categoria": [c["categoria"] for c in CATEGORIAS],
            "seccion": [c["seccion"] for c in CATEGORIAS],
        }
    )


def generar_tiendas() -> pd.DataFrame:
    """Cinco tiendas ficticias del área de Barcelona.

    Las grandes venden más porque su factor (derivado de los m2) entra en la
    Poisson. No es una tienda real: el nombre de la cadena es SportStock.
    """
    metros = [tienda["m2"] for tienda in TIENDAS]
    return pd.DataFrame(
        {
            "tienda_id": np.arange(1, len(TIENDAS) + 1, dtype=np.int64),
            "nombre": [tienda["nombre"] for tienda in TIENDAS],
            "ciudad": [tienda["ciudad"] for tienda in TIENDAS],
            "tipo": ["grande" if m2 >= UMBRAL_M2_GRANDE else "ciudad" for m2 in metros],
            "m2": metros,
        }
    )


def calcular_eventos(
    fechas: pd.DatetimeIndex,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Factor de evento, descuento y flags de calendario, de la misma regla.

    Rebajas: 7-31 de enero y todo julio (1.5x, 30% de descuento).
    Semana del 24 al 30 de noviembre: 1.8x y 25%. El 28 (Black Friday 2025)
    sube a 3x y se queda con el mismo 25%: el descuento no se acumula.
    Navidad (1-24 de diciembre): 1.3x, sin descuento extra. El regalo de
    Navidad no es una rebaja; mezclarlos hincharía el importe a la baja.
    """
    mes = fechas.month.to_numpy()
    dia = fechas.day.to_numpy()
    n_dias = len(fechas)
    factor = np.ones(n_dias, dtype=np.float64)
    descuento = np.zeros(n_dias, dtype=np.float64)

    es_rebajas = ((mes == 1) & (dia >= 7)) | (mes == 7)
    es_semana_bf = (mes == 11) & (dia >= 24) & (dia <= 30)
    es_black_friday = (mes == 11) & (dia == 28)
    es_navidad = (mes == 12) & (dia <= 24)

    factor[es_rebajas] = FACTOR_REBAJAS
    descuento[es_rebajas] = DESCUENTO_REBAJAS
    factor[es_semana_bf] = FACTOR_SEMANA_BLACK_FRIDAY
    descuento[es_semana_bf] = DESCUENTO_BLACK_FRIDAY
    # Se aplica después de la semana para sustituir el 1.8, no multiplicarlo.
    factor[es_black_friday] = FACTOR_BLACK_FRIDAY
    descuento[es_black_friday] = DESCUENTO_BLACK_FRIDAY
    factor[es_navidad] = FACTOR_NAVIDAD
    return factor, descuento, es_rebajas, es_black_friday


def generar_calendario(
    fechas: pd.DatetimeIndex,
    es_rebajas: np.ndarray,
    es_black_friday: np.ndarray,
) -> pd.DataFrame:
    """Un fila por día de 2025. Nombres en español fijos, no dependen del locale.

    ``semana`` es la semana ISO. ``año`` es el año civil: los últimos días de
    diciembre pueden caer en la semana 1 del año ISO siguiente, y se deja así
    a propósito (es la definición ISO, no un error de calendario).
    """
    iso = fechas.isocalendar()
    mes = fechas.month.to_numpy()
    dia_semana = fechas.day_of_week.to_numpy()
    return pd.DataFrame(
        {
            "fecha": fechas.strftime("%Y-%m-%d").tolist(),
            "año": np.full(len(fechas), ANIO, dtype=np.int64),
            "mes": mes.astype(np.int64),
            "nombre_mes": [NOMBRES_MES[m - 1] for m in mes],
            "semana": iso.week.astype(np.int64).to_numpy(),
            "dia_semana": [NOMBRES_DIA[d] for d in dia_semana],
            "es_fin_de_semana": dia_semana >= 5,
            "temporada": [TEMPORADA_POR_MES[m - 1] for m in mes],
            "es_rebajas": es_rebajas.astype(bool),
            "es_black_friday": es_black_friday.astype(bool),
        }
    )


def generar_productos(
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Ficha de 200 productos, demanda base y máscara de rotura.

    El margen es un markup sobre coste, entre el 30% y el 60%:
    precio_venta = precio_coste * (1 + margen). Es la lectura habitual de una
    ficha de compra, no el margen sobre venta.

    La demanda base es la de una tienda de factor 1, en un mes de factor 1 y
    un día laborable, antes de eventos. Los artículos baratos rotan más que el
    equipo caro (un bidón sale más a menudo que un esquí); la raíz cuadrada
    suaviza esa relación para que el caro no quede en cero.

    Devuelve también la base y la máscara porque no forman parte del CSV y la
    simulación las necesita. El orden de las llamadas a ``rng`` es fijo.
    """
    if set(CATALOGO) != {c["categoria"] for c in CATEGORIAS}:
        raise ValueError("El catálogo no cubre exactamente las categorías definidas.")

    nombres: list[str] = []
    marcas: list[str] = []
    costes_base: list[float] = []
    categoria_ids: list[int] = []
    skus: list[str] = []
    for categoria in CATEGORIAS:
        fichas = CATALOGO[categoria["categoria"]]
        if len(fichas) != N_PRODUCTOS_POR_CATEGORIA:
            raise ValueError(
                f"{categoria['categoria']} tiene {len(fichas)} productos; se esperaban 25."
            )
        if len(categoria["factores"]) != 12:
            raise ValueError(f"{categoria['categoria']} no tiene 12 factores mensuales.")
        for orden, (nombre, marca, coste) in enumerate(fichas, start=1):
            nombres.append(nombre)
            marcas.append(marca)
            costes_base.append(float(coste))
            categoria_ids.append(categoria["categoria_id"])
            skus.append(f"{categoria['prefijo_sku']}-{orden:04d}")

    n = len(nombres)
    coste_base = np.array(costes_base, dtype=np.float64)
    # Ruido pequeño: el seed mueve el céntimo, no el orden de magnitud.
    precio_coste = redondear_euros(coste_base * rng.uniform(0.92, 1.08, size=n))
    margen = rng.uniform(0.30, 0.60, size=n)
    precio_venta = redondear_euros(precio_coste * (1.0 + margen))
    precio_venta = np.maximum(precio_venta, redondear_euros(precio_coste + 0.01))

    ruido_demanda = rng.lognormal(mean=0.0, sigma=0.25, size=n)
    factor_precio = np.sqrt(30.0 / precio_coste)
    base = np.clip(factor_precio * ruido_demanda, 0.25, 3.5)

    # high exclusivo: 2..21, ambos incluidos, como pide el contrato.
    lead_time = rng.integers(2, 22, size=n, dtype=np.int64)

    es_rotura = np.zeros(n, dtype=bool)
    es_rotura[indices_productos_rotura()] = True
    # Se les sube la base mínima para que el fallo de parámetros se vea aunque
    # el artículo sea caro y, de natural, rote poco. Si no, un esquí de rotura
    # podría pasar el verano sin llegar a cero y la alerta quedaría vacía.
    base[es_rotura] = np.maximum(base[es_rotura], BASE_MINIMA_ROTURA)
    # En la ficha el plazo parece razonable (mínimo 7 días). El retraso real
    # del proveedor se aplica solo en la simulación: es lo que el maestro no
    # cuenta y las roturas sí delatan.
    lead_time[es_rotura] = np.maximum(lead_time[es_rotura], 7)

    factores = np.array([c["factores"] for c in CATEGORIAS], dtype=np.float64)
    pico_estacional = factores.max(axis=1)
    categoria_idx = np.array(categoria_ids, dtype=np.int64) - 1
    factor_sabado = float(FACTOR_DIA_SEMANA[5])
    factor_tienda_max = float(factores_tienda().max())
    # Cobertura del peor día recurrente (sábado de pico, tienda más grande),
    # no del 3x de Black Friday: ese pico dura un día y lo absorbe el colchón.
    demanda_pico = base * factor_tienda_max * pico_estacional[categoria_idx] * factor_sabado
    stock_minimo = np.maximum(
        5, np.ceil(lead_time * demanda_pico * 1.15).astype(np.int64)
    )
    stock_maximo = stock_minimo + np.maximum(10, np.ceil(demanda_pico * 14).astype(np.int64))

    # Infradimensionado a propósito: el mínimo no cubre ni un par de días de
    # demanda y el máximo apenas un pedido corto. Con el retraso de proveedor,
    # la tasa de reposición queda por debajo de la demanda y aparecen roturas
    # visibles, sobre todo en picos (rebajas, Black Friday, temporada alta).
    stock_minimo[es_rotura] = STOCK_MINIMO_ROTURA
    stock_maximo[es_rotura] = STOCK_MAXIMO_ROTURA

    if np.any(stock_maximo <= stock_minimo):
        raise RuntimeError("stock_maximo debe ser estrictamente mayor que stock_minimo.")
    if np.any(precio_venta <= precio_coste):
        raise RuntimeError("precio_venta debe ser estrictamente mayor que precio_coste.")

    tabla = pd.DataFrame(
        {
            "producto_id": np.arange(1, n + 1, dtype=np.int64),
            "sku": skus,
            "nombre": nombres,
            "categoria_id": np.array(categoria_ids, dtype=np.int64),
            "marca": marcas,
            "precio_coste": precio_coste,
            "precio_venta": precio_venta,
            "stock_minimo": stock_minimo.astype(np.int64),
            "stock_maximo": stock_maximo.astype(np.int64),
            "lead_time_dias": lead_time.astype(np.int64),
        }
    )
    return tabla, base, es_rotura


def calcular_lambda(
    fechas: pd.DatetimeIndex,
    base: np.ndarray,
    factores_estacionales: np.ndarray,
    factor_evento: np.ndarray,
    n_tiendas: int,
) -> np.ndarray:
    """Lambda de la Poisson, forma (días, combinaciones tienda-producto).

    demanda = Poisson(base * factor_tienda * factor_estacional[mes]
                      * factor_dia_semana * factor_evento).

    Se materializa de una vez, no fila a fila. El orden de las columnas es
    tienda-major: para cada tienda, los 200 productos. ``tile`` repite el
    vector de producto; ``repeat`` expande el de tienda. No son intercambiables.
    """
    n_productos = base.shape[0]
    factor_tienda = factores_tienda()
    base_combo = np.tile(base, n_tiendas)
    tienda_combo = np.repeat(factor_tienda, n_productos)
    estacional_combo = np.tile(factores_estacionales, (n_tiendas, 1))

    mes_idx = fechas.month.to_numpy() - 1
    dia_semana = fechas.day_of_week.to_numpy()
    estacional = estacional_combo[:, mes_idx].T
    lam = (
        base_combo[None, :]
        * tienda_combo[None, :]
        * estacional
        * FACTOR_DIA_SEMANA[dia_semana][:, None]
        * factor_evento[:, None]
    )
    if not np.isfinite(lam).all() or np.any(lam <= 0):
        raise RuntimeError("La lambda de demanda tiene ceros o valores no finitos.")
    return lam


def _programar_llegadas(
    llegadas: np.ndarray,
    pendiente: np.ndarray,
    dia_origen: int,
    lead_time: np.ndarray,
    cantidades: np.ndarray,
    indices: np.ndarray,
) -> None:
    """Suma un pedido al día de llegada y a la posición pendiente.

    ``np.add.at`` hace el scatter-add vectorizado: cada combinación puede
    tener un plazo distinto y no hace falta un bucle Python por fila.
    """
    if indices.size == 0:
        return
    destinos = dia_origen + lead_time[indices]
    np.add.at(llegadas, (destinos, indices), cantidades[indices])
    pendiente[indices] += cantidades[indices]


def simular_stock(
    demanda: np.ndarray,
    stock_inicial: np.ndarray,
    stock_minimo: np.ndarray,
    stock_maximo: np.ndarray,
    lead_time_real: np.ndarray,
    mask_sobrestock: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simula el año operando cada día sobre todas las combinaciones a la vez.

    Orden del día, que es el que hace cuadrar la ecuación de stock:
    stock_final(d) = stock_final(d-1) + entradas(d) - salidas(d).
    El 1 de enero no tiene día anterior: el stock inicial es el de apertura,
    y no se arrastra pipeline del año previo salvo en el caso de sobrestock.

    Política mínimo-máximo: si la posición (stock en tienda + pedidos que aún
    no han llegado) cae por debajo del mínimo, se pide la diferencia hasta el
    máximo. El pedido llega al cabo de ``lead_time_real`` días. La venta del
    día es min(demanda, stock tras las entradas): lo que no hay, se pierde.
    No hay stock negativo por construcción.

    Sobrestock (~10% de combinaciones, disjunto de las de rotura):
    arrancan el año con un pedido ya cursado de 2 * stock_maximo + 1 unidades,
    que llega dentro del plazo teórico. Aunque ese día se venda todo lo que
    quepa, el stock queda por encima del máximo. Si más adelante vuelven a
    pedir, la cantidad se multiplica por 3. Es un error de previsión / compra
    oportunista, no un fallo del mínimo-máximo sano.

    Rotura: no se decide aquí. Llega ya cocinada en un lead time real más largo
    que el de la ficha y en un mínimo/máximo que no cubre la demanda. Esta
    función solo ejecuta la política con esos parámetros.
    """
    n_dias, n_combos = demanda.shape
    horizonte = n_dias + int(lead_time_real.max()) + 1
    llegadas = np.zeros((horizonte, n_combos), dtype=np.int64)
    pendiente = np.zeros(n_combos, dtype=np.int64)

    if np.any(mask_sobrestock):
        indices = np.flatnonzero(mask_sobrestock)
        # 2 * máximo + 1 garantiza stock_final > stock_maximo el día que entra,
        # incluso si ese día la demanda se lleva todo el stock previo.
        cantidades = np.zeros(n_combos, dtype=np.int64)
        cantidades[indices] = stock_maximo[indices] * 2 + 1
        _programar_llegadas(llegadas, pendiente, 0, lead_time_real, cantidades, indices)

    stock = stock_inicial.astype(np.int64, copy=True)
    stock_hist = np.zeros((n_dias, n_combos), dtype=np.int64)
    entradas_hist = np.zeros((n_dias, n_combos), dtype=np.int64)
    salidas_hist = np.zeros((n_dias, n_combos), dtype=np.int64)

    for dia in range(n_dias):
        entradas = llegadas[dia].copy()
        pendiente -= entradas
        stock = stock + entradas
        salidas = np.minimum(demanda[dia], stock)
        stock = stock - salidas

        entradas_hist[dia] = entradas
        salidas_hist[dia] = salidas
        stock_hist[dia] = stock

        posicion = stock + pendiente
        necesitan = posicion < stock_minimo
        if not np.any(necesitan):
            continue
        cantidad = np.zeros(n_combos, dtype=np.int64)
        cantidad[necesitan] = stock_maximo[necesitan] - posicion[necesitan]
        sobredimensionar = necesitan & mask_sobrestock
        if np.any(sobredimensionar):
            cantidad[sobredimensionar] = np.maximum(
                cantidad[sobredimensionar] * MULTIPLICADOR_SOBRESTOCK,
                stock_maximo[sobredimensionar] + 1,
            )
        indices = np.flatnonzero(cantidad > 0)
        _programar_llegadas(llegadas, pendiente, dia, lead_time_real, cantidad, indices)

    return stock_hist, entradas_hist, salidas_hist


def construir_ventas(
    fechas_str: np.ndarray,
    salidas: np.ndarray,
    precio_venta: np.ndarray,
    precio_coste: np.ndarray,
    descuento: np.ndarray,
) -> pd.DataFrame:
    """Una fila por fecha-tienda-producto con unidades > 0 (agregado diario).

    No hay tickets: el grano pedido es el día, y es el que cuadra con las
    salidas de stock. importe = unidades * precio_venta * (1 - descuento);
    coste = unidades * precio_coste. El descuento es el de la campaña del día.
    """
    n_productos = precio_venta.shape[0]
    dias, combos = np.nonzero(salidas > 0)
    producto_idx = combos % n_productos
    tienda_idx = combos // n_productos
    unidades = salidas[dias, combos].astype(np.int64)
    importe = redondear_euros(
        unidades * precio_venta[producto_idx] * (1.0 - descuento[dias])
    )
    coste = redondear_euros(unidades * precio_coste[producto_idx])

    # lexsort ordena por la última clave primero: fecha, luego tienda, luego producto.
    orden = np.lexsort((producto_idx, tienda_idx, dias))
    return pd.DataFrame(
        {
            "venta_id": np.arange(1, orden.size + 1, dtype=np.int64),
            "fecha": fechas_str[dias[orden]],
            "tienda_id": (tienda_idx[orden] + 1).astype(np.int64),
            "producto_id": (producto_idx[orden] + 1).astype(np.int64),
            "unidades": unidades[orden],
            "importe": importe[orden],
            "coste": coste[orden],
        }
    )


def construir_stock_diario(
    fechas_str: np.ndarray,
    stock_final: np.ndarray,
    entradas: np.ndarray,
    salidas: np.ndarray,
) -> pd.DataFrame:
    """Snapshot diario de cada combinación tienda-producto, también si no hubo venta.

    El ravel en orden C coincide con repetir la fecha y tilear la combinación:
    dentro de cada día, tienda-major y producto creciente. Así la fila i del
    array es la fila i del CSV, sin un merge posterior.
    """
    n_dias, n_combos = stock_final.shape
    n_productos = n_combos // N_TIENDAS
    combo = np.arange(n_combos)
    tienda_id = combo // n_productos + 1
    producto_id = combo % n_productos + 1
    return pd.DataFrame(
        {
            "fecha": np.repeat(fechas_str, n_combos),
            "tienda_id": np.tile(tienda_id, n_dias).astype(np.int64),
            "producto_id": np.tile(producto_id, n_dias).astype(np.int64),
            "stock_final": stock_final.ravel(),
            "entradas": entradas.ravel(),
            "salidas": salidas.ravel(),
        }
    )


def generar_datos(seed: int = 42) -> dict[str, pd.DataFrame]:
    """Genera las seis tablas en memoria. No escribe a disco.

    Orden de la semilla, que hay que respetar para que el seed sea reproducible:
    1. ruido de precio, margen, ruido de demanda y lead time (en ``generar_productos``);
    2. stock inicial de cada combinación;
    3. la Poisson de todo el año.
    """
    rng = np.random.default_rng(seed)

    categorias = generar_categorias()
    tiendas = generar_tiendas()
    fechas = pd.date_range(f"{ANIO}-01-01", f"{ANIO}-12-31", freq="D")
    if len(fechas) != 365:
        raise RuntimeError(f"Se esperaban 365 días en {ANIO} y hay {len(fechas)}.")

    factor_evento, descuento, es_rebajas, es_black_friday = calcular_eventos(fechas)
    calendario = generar_calendario(fechas, es_rebajas, es_black_friday)
    productos, base, es_rotura = generar_productos(rng)

    n_tiendas = len(tiendas)
    n_productos = len(productos)
    n_combos = n_tiendas * n_productos

    # Orden tienda-major: tile repite el vector de producto (200) una vez por
    # tienda. Tiene que coincidir con calcular_lambda y con el ravel del stock.
    es_rotura_combo = np.tile(es_rotura, n_tiendas)
    # Una de cada nueve combinaciones sanas. 900 candidatas / 9 = 100 exactas.
    candidatos = np.flatnonzero(~es_rotura_combo)
    mask_sobrestock = np.zeros(n_combos, dtype=bool)
    mask_sobrestock[candidatos[::9][:100]] = True
    if int(es_rotura_combo.sum()) != 100 or int(mask_sobrestock.sum()) != 100:
        raise RuntimeError("Rotura y sobrestock deben cubrir el 10% de las combinaciones.")
    if np.any(mask_sobrestock & es_rotura_combo):
        raise RuntimeError("Rotura y sobrestock no pueden solaparse.")

    lead_time = productos["lead_time_dias"].to_numpy(dtype=np.int64)
    lead_time_real = np.tile(lead_time, n_tiendas)
    lead_time_real[es_rotura_combo] += RETRASO_PROVEEDOR_DIAS

    stock_minimo = np.tile(productos["stock_minimo"].to_numpy(dtype=np.int64), n_tiendas)
    stock_maximo = np.tile(productos["stock_maximo"].to_numpy(dtype=np.int64), n_tiendas)
    stock_inicial = rng.integers(stock_minimo, stock_maximo + 1, dtype=np.int64)

    factores = np.array([c["factores"] for c in CATEGORIAS], dtype=np.float64)
    categoria_idx = productos["categoria_id"].to_numpy(dtype=np.int64) - 1
    factores_producto = factores[categoria_idx]
    lam = calcular_lambda(fechas, base, factores_producto, factor_evento, n_tiendas)
    demanda = rng.poisson(lam).astype(np.int64)

    stock_final, entradas, salidas = simular_stock(
        demanda,
        stock_inicial,
        stock_minimo,
        stock_maximo,
        lead_time_real,
        mask_sobrestock,
    )
    if not np.any(stock_final == 0):
        raise RuntimeError("La simulación no ha generado roturas.")
    if not np.any(stock_final > stock_maximo):
        raise RuntimeError("La simulación no ha generado sobrestock.")

    fechas_str = calendario["fecha"].to_numpy()
    ventas = construir_ventas(
        fechas_str,
        salidas,
        productos["precio_venta"].to_numpy(dtype=np.float64),
        productos["precio_coste"].to_numpy(dtype=np.float64),
        descuento,
    )
    stock_diario = construir_stock_diario(fechas_str, stock_final, entradas, salidas)

    return {
        "categorias": categorias,
        "productos": productos,
        "tiendas": tiendas,
        "calendario": calendario,
        "ventas": ventas,
        "stock_diario": stock_diario,
    }


def guardar_csv(tablas: dict[str, pd.DataFrame], output_dir: str | Path) -> None:
    """Escribe las seis tablas en UTF-8, separador coma, sin índice.

    Los importes ya vienen redondeados a 2 decimales y las fechas en ISO.
    """
    destino = Path(output_dir)
    destino.mkdir(parents=True, exist_ok=True)
    for nombre in TABLAS:
        tablas[nombre].to_csv(
            destino / f"{nombre}.csv",
            index=False,
            encoding="utf-8",
        )


def main() -> None:
    """Punto de entrada: genera y deja los CSV en data/raw salvo que se indique otra carpeta."""
    parser = argparse.ArgumentParser(
        description="Genera datos sintéticos de stock de la cadena ficticia SportStock."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Semilla del generador (por defecto 42).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help=(
            "Carpeta de salida. Si es relativa, se interpreta desde el directorio "
            "de trabajo. Por defecto, data/raw de la raíz del proyecto."
        ),
    )
    args = parser.parse_args()
    salida = Path(args.output) if args.output else RAIZ_PROYECTO / "data" / "raw"

    tablas = generar_datos(seed=args.seed)
    guardar_csv(tablas, salida)

    print(f"Datos generados con semilla {args.seed} en {salida}")
    for nombre in TABLAS:
        ruta = salida / f"{nombre}.csv"
        filas = len(tablas[nombre])
        mb = ruta.stat().st_size / (1024 * 1024)
        print(f"  {nombre}.csv: {filas} filas, {mb:.2f} MB")

    stock = tablas["stock_diario"]
    maximos = tablas["productos"].set_index("producto_id")["stock_maximo"]
    n_rotura = int((stock["stock_final"] == 0).sum())
    n_sobre = int((stock["stock_final"].to_numpy() > stock["producto_id"].map(maximos).to_numpy()).sum())
    print(f"  roturas (stock_final = 0): {n_rotura} filas")
    print(f"  sobrestock (stock_final > stock_maximo): {n_sobre} filas")


if __name__ == "__main__":
    main()
