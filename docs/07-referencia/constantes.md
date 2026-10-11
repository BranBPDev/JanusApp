[⬅ Volver al README](../../README.md)

# Constantes y parámetros

## Entrada y medida

| Constante | Valor | Archivo |
|---|---|---|
| `MAX_SIDE` | 768 px | `preprocess.py` |
| `CELL_M` | 0,05 m | `metric.py` |
| `LINE_FRACTION` | 0,5 | `metric.py` |
| `COLOR_TOLERANCE` | 60 | `metric.py` |
| Tolerancia entre medidas de vistas | 6 % | `metric.py` |
| Tolerancia de regularidad de cuadrícula | 8 % | `metric.py` |
| Tolerancia de cuadros cuadrados | 5 % | `metric.py` |

## Forma

| Constante | Valor | Archivo |
|---|---|---|
| `RESOLUTION` | 88 | `pipeline.py` |
| `PAD` | 2 | `pipeline.py` |
| `LOD_TOLERANCE` | 0,02 / 0,04 / 0,08 / 0,15 | `pipeline.py` |
| `PRIMITIVE_GRID_ROUND` | (12,6) (8,4) (6,2) (4,2) | `pipeline.py` |
| `PRIMITIVE_GRID_SHARP` | (16,8) (12,6) (8,4) (8,4) | `pipeline.py` |
| `SHARP_CLEANUP` | 0,03 / 0,03 / 0,05 / 0,05 | `pipeline.py` |
| `EXPONENTS` | 0,12 / 0,25 / 0,45 / 0,7 / 1,0 / 1,5 | `primitive.py` |
| `ACCEPT_IOU` | 0,96 | `primitive.py` |
| Umbral de coherencia de vistas | 0,9 | `pipeline.py` |
| Suavizado Taubin | 5 iter., λ 0,5, μ −0,53 | `pipeline.py`, `mesh_ops.py` |
| Islas eliminadas | < 2 % de la mayor | `mesh_ops.py` |

## Apertura

| Constante | Valor | Archivo |
|---|---|---|
| `WALL` | 0,93 | `cut.py` |
| `OPEN_ANGLE` | 75° | `cut.py` |
| `AXIS` | (1, 0, 0) | `cut.py` |

## Textura

| Constante | Valor | Archivo |
|---|---|---|
| `cap` (atlas) | 256 px | `atlas.py` |
| `GAP` / `BLOCK` | 3 / 8 | `atlas.py` |
| `NEUTRAL` | (205, 205, 210) | `atlas.py` |
| `TEX_WIDTH` (equirrectangular) | 256 (256×128) | `ellipsoid.py` |
| `STRIP` | 8 filas | `ellipsoid.py` |
| `PREVIEW_GRID` | (32, 16) | `ellipsoid.py` |

## Interfaz y visor

| Constante | Valor | Archivo |
|---|---|---|
| Ventana principal | 1280×800 (mín. 1000×650) | `main_window.py` |
| Barra lateral | 220 px | `main_window.py` |
| `PREVIEW` (casilla) | 84 px | `shape_page.py` |
| Panel izquierdo de Forma | 410 px | `shape_page.py` |
| Zoom del visor | 0,3 – 6,0 | `viewer.py` |
| Luz del visor | (−0,4; 0,6; 0,7) | `render.py` |

## Actualización y red

| Constante | Valor | Archivo |
|---|---|---|
| Timeout `http_get` | 6 s | `download_util.py` |
| Timeout `download_file` | 30 s | `download_util.py` |
| `CHUNK` | 512 KB | `download_util.py` |
| Espera al cierre del proceso | 60 s | `update.ps1` |
| Reintentos de archivo | 20 × 500 ms | `update.ps1` |
| Cierre limpio / forzado | 800 ms / 3000 ms | `app_manager.py` |
| Log rotativo | 5 MB × 3 | `logger_util.py` |
