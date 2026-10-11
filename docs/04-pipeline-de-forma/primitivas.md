[⬅ Volver al README](../../README.md)

# Primitivas y elipsoides (`primitive.py`, `ellipsoid.py`)

## Supercuádricas

Se ajusta un supercuádrico para ver si una forma simple explica las siluetas.

- Parámetros `(axis, e1, e2)`: eje principal (0, 1 o 2) y exponentes.
- `EXPONENTS = (0.12, 0.25, 0.45, 0.7, 1.0, 1.5)`: 1 = redondo, valores bajos = aristas vivas.
- `fit_primitive` prueba todas las combinaciones, calcula el **IoU** medio entre las proyecciones del sólido y las siluetas, y acepta la mejor si `IoU ≥ ACCEPT_IOU = 0,96`.
- `is_round(params)`: `e1 ≥ 0,7` y `e2 ≥ 0,7`.
- `is_ellipsoid(params)`: `e1 == 1,0` y `e2 == 1,0`.

## Malla de la primitiva (`primitive_mesh`)

Malla regular, simétrica y cerrada, apoyada en `y = 0`, con un polo en cada extremo del eje y anillos intermedios. Los parámetros `(lados, anillos)` por LOD:

| LOD | Redondas | Con aristas |
|---|---|---|
| 0 | 12 × 6 | 16 × 8 |
| 1 | 8 × 4 | 12 × 6 |
| 2 | 6 × 2 | 8 × 4 |
| 3 | 4 × 2 | 8 × 4 |

En las no redondas se aplica además una limpieza con `decimate` (`SHARP_CLEANUP = 0,03; 0,03; 0,05; 0,05` × tamaño) que une caras planas redundantes. El ángulo de pliegue de normales es 60° en primitivas redondas y 40° en el resto.

## Esfera / elipsoide: objeto paramétrico

Cuando la primitiva es un elipsoide **no se guarda ninguna malla**:

1. `bake_equirect` pinta una textura equirrectangular de 256×128 mezclando las vistas con peso `(n·dirección)^4`.
2. `preview_model` genera una malla (32×16) **solo para la vista previa** y, si hay marca de corte, la divide en pieza fija y móvil.
3. `descriptor` construye lo único que se almacena:

```json
{
  "type": "sphere | ellipsoid",
  "semi_axes": [ax, ay, az],
  "center": [0.0, ay, 0.0],
  "texture": "texture.png",
  "uv": "equirect: u = atan2(x, z) / 2pi + 0.5 ...; v = 0.5 - asin(y / semi_axis_y) / pi",
  "triangles": 0,
  "opening": { "plane_point": [], "plane_normal": [], "hinge": [], "axis": [], "open_angle_deg": 75, "wall": 0.93, "interior_color": {} }
}
```

`type` es `sphere` si el cociente entre el semieje mayor y el menor es < 1,03. `opening` solo aparece si el objeto se abre.

La textura equirrectangular tiene el frente en `u = 0,5` y el polo +Y arriba. Las tapas interiores usan unas filas extra de color plano que solo existen en la vista previa.
