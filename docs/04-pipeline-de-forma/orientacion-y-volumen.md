[⬅ Volver al README](../../README.md)

# Orientación de vistas y volumen (`field.py`, `surface_nets.py`, `mesh_ops.py`)

## Rejilla y siluetas

- `grid_shape(dims, resolucion)`: calcula el tamaño de la rejilla; la celda es `max(dims)/resolución` y cada eje tiene como mínimo 4 celdas.
- `make_arrays(masks, shape)`: remuestrea cada silueta a la rejilla (BOX al reducir, BILINEAR al ampliar).

## Casco visual (`compose`)

El volumen es el **mínimo de las siluetas proyectadas** (casco visual suave). Cada vista se proyecta sobre un eje:

| Vista | Eje | Transformación |
|---|---|---|
| frente | Z | `[::-1].T` |
| detrás | Z | `[::-1, ::-1].T` |
| derecha | X | `[::-1]` (más volteo opcional `fr`) |
| izquierda | X | `[::-1, ::-1]` (volteo opcional `fl`) |
| arriba | Y | `.T` (volteo opcional `ft`) |
| abajo | Y | `[::-1].T` (volteo opcional `fb`) |

## Detección de orientación (`detect_orientation`)

Prueba todas las combinaciones de volteo de las vistas laterales y cenitales presentes (resolución 48), puntúa cada una con la fracción de silueta cubierta por la proyección del volumen y elige la mejor. Entre las que quedan a 0,004 de la mejor se prefiere la de **menos volteos**. Devuelve `(flips, puntuación)`; si la puntuación es < 0,9 se avisa de incoherencia entre vistas.

## Surface Nets (`surface_nets.py`)

Extrae la superficie del campo escalar (iso = 0,5), vectorizado con numpy:

1. Marca las celdas mixtas (algunas esquinas dentro, otras fuera).
2. Un vértice por celda: media de los cruces de aristas con la superficie.
3. Un quad por cada arista de la rejilla que cambia de signo, orientado hacia fuera.
4. Cada quad se divide por la diagonal más corta.

Requiere que el exterior rodee todo el campo (el pipeline añade `PAD = 2`).

## Post-proceso del volumen (`pipeline` + `mesh_ops`)

1. `RESOLUTION = 88` para la rejilla.
2. `remove_small_components`: elimina islas con menos del 2 % de las caras de la mayor.
3. `taubin_smooth` (5 iteraciones, λ = 0,5, μ = −0,53): suaviza sin encoger el volumen.
4. Se centra en X/Z y se apoya en `y = 0`.

## Utilidades de `mesh_ops.py`

`unique_edges`, `compact`, `vertex_normals`, `is_watertight`, `signed_volume`, `crease_normals` (normales por esquina, suaves por debajo del ángulo de pliegue) y `build_attributes` (vértices únicos duplicando donde cambian normal o UV).
