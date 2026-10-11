[⬅ Volver al README](../../README.md)

# Pipeline completo de forma

Punto de entrada: `generate_shape(view_paths, grid_paths, progress)` en `app/shape/pipeline.py`. Devuelve un `ShapeResult`.

## Sistema de coordenadas

X a la derecha (visto desde el frente), Y arriba, Z hacia la cámara frontal. El objeto se apoya en `y = 0` y se centra en X/Z.

## Etapas

| # | Etapa | Módulo | Detalle |
|---|---|---|---|
| 1 | Validar entradas | `pipeline` | Frente + lateral; malla por cada vista |
| 2 | Leer siluetas | `preprocess` | [Preprocesado](preprocesado.md) |
| 3 | Analizar mallas | `metric` | [Escala métrica](escala-metrica.md) |
| 4 | Calcular dimensiones | `metric` | Ancho, alto y fondo en metros |
| 5 | Buscar apertura | `opening` | [Apertura](apertura.md) |
| 6 | Orientación de vistas | `field` | [Orientación y volumen](orientacion-y-volumen.md) |
| 7 | Ajustar primitiva | `primitive` | [Primitivas](primitivas.md) |
| 8a | Elipsoide → descriptor | `ellipsoid` | 0 triángulos |
| 8b | Primitiva → malla en 4 LODs | `primitive`, `qem` | |
| 8c | Volumen → superficie y 4 LODs | `field`, `surface_nets`, `mesh_ops`, `qem` | [Decimación](decimacion-lods.md) |
| 9 | Atlas de textura | `atlas` | [Atlas](atlas-y-texturas.md) |
| 10 | Construir piezas | `cut`, `mesh_ops` | Fija + móvil si hay corte |
| 11 | Guardar | `project`, `export` | [Exportación](exportacion.md) |

## Decisión de forma

```
fit_primitive(siluetas) → IoU ≥ 0,96 ?
   ├─ sí, e1 = e2 = 1 → ELIPSOIDE / ESFERA (descriptor + textura equirrectangular)
   ├─ sí, otro        → PRIMITIVA (supercuádrica) en 4 LODs
   └─ no              → VOLUMEN de las vistas (Surface Nets) en 4 LODs
```

## Progreso (fracción aproximada)

| Fracción | Mensaje |
|---|---|
| 0–0,06 | Leyendo vista ... |
| 0,08 | Analizando la forma del objeto... |
| 0,2–0,6 | Generando / Optimizando LODn... |
| 0,68 | Preparando textura... |
| 0,78 | Construyendo el modelo... |
| 0,92 | Modelo generado |
| 0,95 | Guardando proyecto... (ShapeWorker) |
| 1,0 | Completado |

## ShapeResult

| Campo | Contenido |
|---|---|
| `lods` | Lista de `Model` (uno por LOD) |
| `warnings` | Avisos para mostrar al usuario |
| `info` | Modo, primitiva, IoU, apertura, watertight, textura, tiempo, triángulos, tamaño, métricas |
| `descriptor` | Descriptor paramétrico (solo esfera/elipsoide) |
| `texture` | Textura que acompaña al descriptor |
| `marks` | Marcas leídas de cada malla |

## Modelo de datos (`model.py`)

- `Part`: `name`, `vertices (n,3)`, `faces (m,3)`, `normals (n,3)`, `uvs (n,2)`, `parent`, `origin` (pivote), `axis`, `open_angle`.
- `Model`: `parts`, `texture (h,w,4) uint8`. Propiedades: `triangles`, `vertex_count`, `openable`, `size`. Método `scaled(sxz, sy)` reescala vértices, normales y pivotes.
- Piezas: `body` (sin corte) o `fixed` + `movable` (con corte).
