[⬅ README](../README.md)

# 📚 Referencia

## 🔢 Constantes

| Grupo | Constante | Valor | Archivo |
|---|---|---|---|
| **Entrada** | `MAX_SIDE` | 768 px | `preprocess` |
| | `CELL_M` · `LINE_FRACTION` · `COLOR_TOLERANCE` | 0,05 m · 0,5 · 60 | `metric` |
| | Tolerancias: vistas / cuadrícula / cuadros | 6 % / 8 % / 5 % | `metric` |
| **Forma** | `RESOLUTION` · `PAD` | 88 · 2 | `pipeline` |
| | `LOD_TOLERANCE` | 0,02 · 0,04 · 0,08 · 0,15 | `pipeline` |
| | `PRIMITIVE_GRID_ROUND` | (12,6) (8,4) (6,2) (4,2) | `pipeline` |
| | `PRIMITIVE_GRID_SHARP` | (16,8) (12,6) (8,4) (8,4) | `pipeline` |
| | `SHARP_CLEANUP` | 0,03 · 0,03 · 0,05 · 0,05 | `pipeline` |
| | Coherencia de vistas | 0,9 | `pipeline` |
| | `EXPONENTS` · `ACCEPT_IOU` | 0,12 … 1,5 · 0,96 | `primitive` |
| **Salientes** | `MIN_INLIERS` · `MAX_EXTRAS` · `AXIS_TOLERANCE` | 0,8 · 0,25 · 0,08 | `protrusion` |
| | `RESOLUTION` · `GAP` · `EMBED` | 176 · 1,5 · 1,5 voxels | `protrusion` |
| | `DECIMATE` · `ATLAS_CAP` | 0,002 · 512 | `protrusion` |
| **Apertura** | `WALL` · `OPEN_ANGLE` · `AXIS` | 0,93 · 75° · (1,0,0) | `cut` |
| **Textura** | `cap` del atlas · `GAP` · `BLOCK` | 256 · 3 · 8 | `atlas` |
| | `NEUTRAL` | (205, 205, 210) | `atlas` |
| | `TEX_WIDTH` · `STRIP` · `MESH_GRID` | 512 (512×256) · 8 · (96, 48) | `ellipsoid` |
| | `MAX_CELL` (interior) | 512 | `interior` |
| **Interfaz** | Ventana · barra lateral | 1280×800 (mín. 1000×650) · 220 px | `main_window` |
| | Panel izquierdo de Forma · casilla · miniatura | 410 · 84 · 64 px | `shape_page` · `widgets` · `home_page` |
| | Zoom del visor · luz | 0,3–6,0 · (−0,4; 0,6; 0,7) | `viewer` · `render` |
| **Red** | `http_get` · `download_file` · `CHUNK` | 6 s · 30 s · 512 KB | `download_util` |
| | Espera al cierre · reintentos | 60 s · 20 × 500 ms | `update.ps1` |
| | Cierre limpio / forzado · log | 800 / 3000 ms · 5 MB × 3 | `app_manager` · `logger_util` |

## 🧾 `manifest.json`

`app/projects/<nombre>/manifest.json` (UTF-8, indentación 4).

```json
{
  "name": "starterball",
  "updated": "2026-10-14T00:52:11",
  "views":     { "front": "views/front.png" },
  "grids":     { "front": "grids/front.png" },
  "interiors": { "movable": "interiors/movable.png", "fixed": "interiors/fixed.png" },
  "annotations": {
    "left": [ { "color": "#ff0000", "style": "continua", "components": 1,
                "bbox_m": [0.0, 0.1, 0.4, 0.1], "points_m": [[0.2, 0.1]],
                "segments_m": [[[0.0, 0.1], [0.4, 0.1]]] } ]
  },
  "shape": {
    "parts": [], "lods": [], "primitive_object": null,
    "mode": "primitiva", "primitive": { "type": "sphere" }, "primitive_iou": 0.92,
    "openable": true, "texture": [1024, 512], "seconds": 0.0, "triangles": [11198],
    "size": [0.225, 0.2352, 0.2324],
    "extras": { "triangles": 526 },
    "metric": { "cell_m": 0.05, "height_m": 0.0, "width_m": 0.0, "depth_m": 0.0 }
  },
  "phases": { "shape": true, "texture": true, "collision": false, "rig": false }
}
```

| Campo | Descripción |
|---|---|
| `views` · `grids` · `interiors` | Rutas relativas de las copias guardadas |
| `annotations` | Marcas leídas de cada malla (metros) |
| `shape.parts` | `name`, `parent`, `origin`, `axis`, `open_angle_deg` |
| `shape.lods` | Por LOD: `level`, `glb`, `triangles`, `vertices` |
| `shape.primitive_object` | Descriptor paramétrico o `null` |
| `shape.mode` | `"primitiva"` o `"volumen"` |
| `shape.primitive_iou` | Ajuste a las siluetas (en cuerpo + salientes, fracción de contorno que encaja) |
| `shape.extras` | Triángulos de los salientes (solo cuerpo + salientes) |
| `shape.size` | Ancho, alto y fondo del objeto completo (m) |
| `phases` | `shape`, `texture`, `collision`, `rig` (las no tocadas se conservan) |

**Descriptor paramétrico** (`primitive_object`): `type` (`sphere` si semieje mayor/menor < 1,03, si no `ellipsoid`), `semi_axes`, `center`, `texture`, `uv` (equirrectangular), `triangles`, `glb`, `extras` (si hay salientes: solo existen en el `.glb`) y, si se abre, `opening`: `plane_point`, `plane_normal`, `hinge`, `axis`, `open_angle_deg`, `wall`, `interior_textures`, `button` (`center_xy`, `radius`) e `interior_color`.

## 📖 Glosario

| Término | Significado |
|---|---|
| **Vista** | Imagen 2D del objeto desde una de las seis direcciones |
| **Malla** | Imagen con cuadrícula de 5 cm por cuadro (escala) y marcas de color. *No* es una malla 3D |
| **Marca** | Dibujo de color sobre la malla: 🔴 corte · 🟢 móvil · 🔵 bisagra · 🟡 botón · 🟣 saliente |
| **Saliente** | Parte que sobresale de un cuerpo redondo (tapa, cierre…) |
| **Casco visual** | Volumen 3D de intersectar las siluetas proyectadas |
| **Surface Nets** · **Taubin** · **QEM** | Extracción de superficie · suavizado sin encoger · simplificación por error cuádrico |
| **Supercuádrico** · **IoU** | Forma de caja a elipsoide por exponentes · intersección sobre unión |
| **Paramétrico** | Esfera/elipsoide guardada como descriptor + textura |
| **LOD** | Nivel de detalle (LOD0 = el mayor) |
| **Atlas** · **Chart** · **UV** | Textura única · región de una vista · coordenadas de textura |
| **Pieza fija / móvil** | Base y tapa de un objeto que se abre; bisagra con eje X |
| **GLB** | glTF 2.0 binario |
| **Fase** | Etapa de la cadena: forma, texturas, colisión, esqueleto |
| **Frozen** | Ejecutándose desde el `.exe` (`IS_FROZEN`) |

## 🚧 Limitaciones y estado (v0.0.2)

| Sección | Estado |
|---|---|
| Inicio · Forma | ✅ Implementadas |
| Texturas · Colisión · Esqueleto · Visor 3D | ⏳ «Próximamente» (la textura básica y el visor ya viven en Forma; el manifest reserva `collision` y `rig`) |

- **Plataforma**: solo Windows.
- **Entrada**: una malla por cada vista; mínimo frente + lateral; sin cuadrícula regular no se genera.
- **Apertura**: eje X fijo y 75°; el corte debe ser un único contorno cerrado; dos piezas huecas con cúpula interior simple; el corte desde el frente solo admite líneas horizontales.
- **Salientes**: solo sobre cuerpos elípticos; altura = la que dan las siluetas (sin concavidades); la forma en planta sale de las marcas violeta.
- **Volumen**: casco visual, sin concavidades que las siluetas no muestren.
- **Textura**: atlas limitado a 256 px (512 en salientes).
- **Rendimiento**: `qem.py` es Python puro (lo más lento con mallas grandes).
- **Visor**: por software, con orden de profundidad por triángulo (puede mostrar artefactos).
- **Paramétricos**: el motor que los use aporta su esfera/elipsoide y UV equirrectangular, o usa el `.glb`.
- **Actualización**: solo en el `.exe`.
