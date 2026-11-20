"""Hace importable `src` sin instalar el proyecto.

`pytest.ini` también declara `pythonpath`, pero insertar la ruta aquí cubre
ejecuciones en las que esa opción no se aplique. No se toca el entorno virtual
ni se instala el paquete: el portfolio tiene que poder correr con lo ya dado.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
ruta = str(SRC)
if ruta not in sys.path:
    sys.path.insert(0, ruta)
