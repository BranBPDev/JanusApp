[⬅ README](../README.md)

# 📚 Referencia

## 🔢 Constantes

| Grupo | Constante | Valor | Archivo |
|---|---|---|---|
| **JSON** | `CANVAS` · `FILL` · `MIN_SIDE_PX` | 640 px · 0,94 · 12 px | `spec/schema` |
| | `MARGIN` · `INTERIOR_PX` · `FILL_TOLERANCE` | 6 px · 512 px · 3 % | `spec/blueprint` |
| | `SS` (supermuestreo) | 2 | `spec/raster` |
| **Forma** | `RESOLUTION` · `RESOLUTION_RIG` · `PAD` | 88 · 128 · 2 | `pipeline` |
| | `LOD_TOLERANCE` | 0,02 · 0,04 · 0,08 · 0,15 | `pipeline` |
| | `LOD_TOLERANCE_RIG` | 0,004 · 0,008 · 0,016 · 0,03 | `pipeline` |
| | `PRIMITIVE_GRID_ROUND` | (12,6) (8,4) (6,2) (4,2) | `pipeline` |
| | `PRIMITIVE_GRID_SHARP` | (16,8) (12,6) (8,4) (8,4) | `pipeline` |
| | `SHARP_CLEANUP` | 0,03 · 0,03 · 0,05 · 0,05 | `pipeline` |
| | `EXPONENTS` · `ACCEPT_IOU` | 0,12 … 1,5 · 0,96 | `geometry/primitive` |
| **Salientes** | `MIN_INLIERS` · `MAX_EXTRAS` · `AXIS_TOLERANCE` | 0,8 · 0,25 · 0,08 | `geometry/protrusion` |
| | `COARSE` · `RESOLUTION` · `SMOOTH` | 96 · 360 · 3 | `geometry/protrusion` |
| | `GAP` · `EMBED` · `DECIMATE` · `ATLAS_CAP` | 2 · 4 voxels · 0,002 · 512 | `geometry/protrusion` |
| **Relieves** | `EMBED` · `MAX_MESH` | 3 mm · 4000 vértices | `geometry/relief` |
| **Apertura** | `WALL` · `OPEN_ANGLE` · `AXIS` | 0,93 · 75° · (1,0,0) | `geometry/cut` |
| **Esqueleto** | `MAX_JOINTS` · `INFLUENCES` · `FALLOFF` | 60 · 4 · 4,0 | `rig/skeleton` |
| **Textura** | `GAP` · `BLOCK` · `NEUTRAL` | 3 · 8 · (205, 205, 210) | `texture/atlas` |
| | `TEX_WIDTH` · `STRIP` · `MESH_GRID` | 512 (512×256) · 8 · (96, 48) | `geometry/ellipsoid` |
| | `MAX_CELL` (interior) | 512 | `texture/interior` |
| **IA** | dim · cabezas · capas · ff · contexto | 128 · 4 · 3 · 512 · 176 | `testing/ia/entrenar` |
| | Palabras de la petición · fichas nuevas máx. | 120 · 60 | `fast/modelo` |
| | Umbral de confianza para avisar | 0,55 | `fast/asistente` |
| | `MAX_LIT` (colores y medidas por petición) | 6 + 6 | `fast/texto` |
| | Registro: tamaño máx. antes de rotar | 8 MB | `fast/registro` |
| **Imágenes** | `SIDE` · `CLUSTERS` · `MERGE_DIST` | 200 px · 6 · 34 | `fast/imagen3d` |
| | `MIN_BLOB` · `MAX_LAYERS` | 0,4 % · 60 | `fast/imagen3d` |
| | `DEFAULT_HEIGHT` · `DEPTH_GUESS` | 0,3 m · 0,7 | `fast/imagen3d` |
| **Interfaz** | Ventana · barra lateral | 1280×800 (mín. 1000×650) · 220 px | `main_window` |
| | Chat · miniatura de Inicio · deshacer | 430 px · 64 px · 30 pasos | `shape_page` · `home_page` · `ai_chat` |
| | Luz del visor | (−0,4; 0,6; 0,7) | `render` |
| **Hilos** | `WORKERS` | min(8, CPU) | `pool_util` |
| **Red** | `http_get` · `download_file` · `CHUNK` | 6 s · 30 s · 512 KB | `download_util` |
| | Espera al cierre · reintentos | 60 s · 20 × 500 ms | `update.ps1` |
| | Cierre limpio / forzado · log | 800 / 3000 ms · 5 MB × 3 | `app_manager` · `logger_util` |

## 🧾 `manifest.json`

`app/projects/<nombre>/manifest.json` (UTF-8, indentación 4).

```json
{
  "name": "starterball",
  "updated": "2026-10-24T12:00:00",
  "source": "source/objeto.json",
  "annotations": {
    "derecha": [ { "color": "#ff0000", "style": "continua", "components": 1,
                   "bbox_m": [0.0, 0.1, 0.4, 0.1], "points_m": [[0.2, 0.1]],
                   "segments_m": [[[0.0, 0.1], [0.4, 0.1]]] } ]
  },
  "shape": {
    "parts": [], "lods": [], "primitive_object": null,
    "mode": "primitiva", "primitive": { "type": "sphere" }, "primitive_iou": 0.92,
    "openable": true, "texture": [1024, 512], "seconds": 0.0, "triangles": [11198],
    "size": [0.225, 0.2352, 0.2324],
    "extras": { "triangles": 526 },
    "metric": { "height_m": 0.2, "width_m": 0.2, "depth_m": 0.2 },
    "skeleton": null
  },
  "phases": { "shape": true, "texture": true, "collision": false, "rig": false }
}
```

| Campo | Descripción |
|---|---|
| `source` | Ruta del JSON con el que se generó (`source/objeto.json`); el lápiz de Inicio lo reabre |
| `annotations` | Marcas del JSON (corte, bisagra, botón…) por vista |
| `shape.parts` | `name`, `parent`, `origin`, `axis`, `open_angle_deg` |
| `shape.lods` | Por LOD: `level`, `glb`, `triangles`, `vertices` |
| `shape.primitive_object` | Descriptor paramétrico o `null` |
| `shape.mode` | `"primitiva"` o `"volumen"` |
| `shape.primitive_iou` | Ajuste a las siluetas (en cuerpo + salientes, fracción de contorno que encaja) |
| `shape.extras` | Triángulos de los salientes y relieves (solo cuerpo + salientes) |
| `shape.size` | Ancho, alto y fondo del objeto completo (m) |
| `shape.skeleton` | Huesos y pesos, o `null` |
| `phases` | `shape`, `texture`, `collision`, `rig` (las no tocadas se conservan) |

**Descriptor paramétrico** (`primitive_object`): `type` (`sphere` si semieje mayor/menor < 1,03, si no `ellipsoid`), `semi_axes`, `center`, `texture`, `uv` (equirrectangular), `triangles`, `glb`, `extras` (si hay salientes o relieves: solo existen en el `.glb`) y, si se abre, `opening`: `plane_point`, `plane_normal`, `hinge`, `axis`, `open_angle_deg`, `wall`, `interior_textures`, `button` (`center_xy`, `radius`) e `interior_color`.

## 📖 Glosario

| Término | Significado |
|---|---|
| **Objeto (JSON)** | Archivo `janus.objeto/1` que describe el objeto entero ([formato](objeto-json.md)) |
| **Vista** | Dibujo del objeto desde una de las seis direcciones, calculado a partir de las capas del JSON |
| **Capa** | Forma (círculo, elipse, rect, polígono, línea) con una textura; se pintan en orden |
| **Textura** | Material con nombre: color, degradado o veta |
| **Tallado** | Efecto de grabado o relieve en la textura que solo modula el brillo |
| **Relieve** | Pieza que sobresale de un cuerpo esférico y sigue su curvatura (franja, cadena, cuerda, pieza, trazo, malla) |
| **Marca** | Dato de apertura o esqueleto: corte, mueve, bisagra, botón, saliente, huesos |
| **Saliente** | Parte que sobresale de un cuerpo redondo (tapa, cierre…) |
| **Blueprint** | El JSON ya interpretado: siluetas con color, marcas e interiores en memoria |
| **Casco visual** | Volumen 3D de intersectar las siluetas proyectadas |
| **Surface Nets** · **Taubin** · **QEM** | Extracción de superficie · suavizado sin encoger · simplificación por error cuádrico |
| **Supercuádrico** · **IoU** | Forma de caja a elipsoide por exponentes · intersección sobre unión |
| **Paramétrico** | Esfera/elipsoide guardada como descriptor + textura |
| **LOD** | Nivel de detalle (LOD0 = el mayor) |
| **Atlas** · **Chart** · **UV** | Textura única · región de una vista · coordenadas de textura |
| **Pieza fija / móvil** | Base y tapa de un objeto que se abre; bisagra con eje X |
| **GLB** | glTF 2.0 binario |
| **Programa (IA)** | Lista corta de órdenes que escribe el modelo y ejecuta la aplicación |
| **Ficha de contexto** | Palabra que describe al modelo cómo es el objeto actual |
| **Starterball** | Macro de la IA: esfera con banda y botón, cuerda roja, tapa dorada y triskel tallado |
| **Fase** | Etapa de la cadena: forma, texturas, colisión, esqueleto |
| **Frozen** | Ejecutándose desde el `.exe` (`IS_FROZEN`) |

## 🚧 Limitaciones y estado (v0.0.2)

| Sección | Estado |
|---|---|
| Inicio · Forma (chat, IA, visor) | ✅ Implementadas |
| Texturas · Colisión · Esqueleto · Visor 3D | ⏳ «Próximamente» (la textura básica, el esqueleto y el visor ya viven en Forma) |

- **Plataforma**: solo Windows.
- **IA**: construye con sus piezas o con imágenes; no inventa formas ni lee archivos 3D. Sus aciertos dependen de lo entrenada que esté ([IA integrada](ia.md)).
- **Imágenes**: hace falta frente + lateral con el nombre de la vista; con una sola se estima la otra; las fotos en perspectiva no valen; los fondos deben ser lisos o transparentes; los agujeros pasantes del objeto se rellenan. El SVG se dibuja de forma sencilla (sin transformaciones).
- **Tallado**: solo sobre lo dibujado en la textura, no sobre relieves que sobresalen.
- **Apertura**: eje X fijo y 75°; el corte debe ser un único contorno cerrado; dos piezas huecas con cúpula interior simple; el corte desde el frente solo admite líneas horizontales.
- **Salientes y relieves**: solo sobre cuerpos esféricos o elípticos; los salientes toman la altura de las siluetas (sin concavidades).
- **Volumen**: casco visual, sin concavidades que las siluetas no muestren; con pocas vistas sale poco detallado.
- **Textura**: atlas limitado a 256 px (512 en salientes).
- **Rendimiento**: `qem.py` es Python puro (lo más lento con mallas grandes).
- **Visor**: por software, con orden de profundidad por triángulo (puede mostrar artefactos).
- **Paramétricos**: el motor que los use aporta su esfera/elipsoide y UV equirrectangular, o usa el `.glb`.
- **Actualización**: solo en el `.exe`.
