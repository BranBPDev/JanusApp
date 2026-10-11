[⬅ Volver al README](../../README.md)

# Formato de `manifest.json`

Se escribe en `app/projects/<nombre>/manifest.json` (UTF-8, indentación 4).

```json
{
  "name": "pokeball",
  "updated": "2026-10-11T17:30:00",
  "views":  { "front": "views/front.png", "left": "views/left.png" },
  "grids":  { "front": "grids/front.png", "left": "grids/left.png" },
  "annotations": {
    "left": [
      {
        "color": "#ff0000",
        "style": "continua",
        "components": 1,
        "bbox_m": [0.0, 0.1, 0.4, 0.1],
        "points_m": [[0.2, 0.1]],
        "segments_m": [[[0.0, 0.1], [0.4, 0.1]]]
      }
    ]
  },
  "shape": {
    "parts": [],
    "lods": [],
    "primitive_object": null,
    "mode": "volumen",
    "primitive": null,
    "primitive_iou": 0.0,
    "openable": false,
    "watertight": true,
    "texture": [256, 256],
    "seconds": 0.0,
    "triangles": [],
    "size": [0.0, 0.0, 0.0],
    "metric": { "cell_m": 0.05, "height_m": 0.0, "width_m": 0.0, "depth_m": 0.0 }
  },
  "phases": { "shape": true, "texture": true, "collision": false, "rig": false }
}
```

## Campos

| Campo | Descripción |
|---|---|
| `name` | Nombre del objeto |
| `updated` | Fecha/hora ISO de la última generación |
| `views` / `grids` | Rutas relativas a las imágenes copiadas |
| `annotations` | Marcas leídas de cada malla (ver [Escala métrica](../04-pipeline-de-forma/escala-metrica.md)); coordenadas en metros |
| `shape.parts` | Piezas del LOD0: `name`, `parent`, `origin`, `axis`, `open_angle_deg` |
| `shape.lods` | Por LOD: `level`, `glb`, `triangles`, `vertices` |
| `shape.primitive_object` | Descriptor paramétrico (esfera/elipsoide) o `null` |
| `shape.mode` | `"primitiva"` o `"volumen"` |
| `shape.primitive` | `{axis, e1, e2}`, `{type}` (elipsoide) o `null` |
| `shape.primitive_iou` | Ajuste de la primitiva a las siluetas |
| `shape.openable` | Si el objeto se abre |
| `shape.watertight` | Si la malla LOD0 es estanca (solo objetos con malla) |
| `shape.texture` | `[alto, ancho]` de la textura |
| `shape.seconds` | Tiempo de generación |
| `shape.triangles` | Triángulos por LOD (`[0]` si es paramétrico) |
| `shape.size` | Ancho, alto y fondo en metros |
| `shape.metric` | Escala usada y dimensiones medidas |
| `phases` | Estado de cada fase: `shape`, `texture`, `collision`, `rig` |

## Notas

- Si el manifest ya existía, se conserva el valor de las fases que no se tocan (`collision`, `rig`).
- `shape.parts` y `shape.lods` están vacíos en los objetos paramétricos.
- El descriptor paramétrico se documenta en [Primitivas y elipsoides](../04-pipeline-de-forma/primitivas.md).
