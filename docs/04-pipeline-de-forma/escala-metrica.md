[⬅ Volver al README](../../README.md)

# Escala métrica y análisis de mallas (`metric.py`)

## Constantes

| Constante | Valor | Significado |
|---|---|---|
| `CELL_M` | 0,05 | Metros que mide siempre un cuadro de la malla |
| `LINE_FRACTION` | 0,5 | Una línea ocupa al menos la mitad del lado de la imagen |
| `COLOR_TOLERANCE` | 60 | Distancia de color (suma de canales) para distinguir tinta/fondo |

## `analyze_overlay(path, original_size, box_px, cell_m)`

1. **Tinta**: si > 20 % de los píxeles tiene transparencia, tinta = alfa > 40; si no, píxeles que difieren del color mediano del borde.
2. **Líneas candidatas**: columnas y filas cuyo perfil de tinta ≥ 0,5, agrupadas por contigüidad (centro y color medio).
3. **Cuadrícula** (`_grid_lines`): se queda con las líneas del color dominante (cuantizado en pasos de 48); las marcas largas de otro color se descartan.
4. **Separación** (`_spacing`): mínimo 3 líneas, separación ≥ 4 px y desviación ≤ 8 %; tolera líneas ausentes. Si falla → `None` (error «No se detecta una cuadrícula regular...»).
5. `cell_px` = media de las separaciones horizontal y vertical (aviso si difieren > 5 %).
6. **Marcas**: lo que no es cuadrícula. Se agrupan por color (cuantizado en pasos de 64), se ignoran grupos de < 12 píxeles y se separan en componentes conexas (8 vecinos, ≥ 3 píxeles).

## Estilo de cada marca

| Estilo | Condición |
|---|---|
| `puntos` | ≥ 4 componentes y tamaño mediano ≤ 0,12·celda + 2 px |
| `discontinua` | ≥ 4 componentes y tamaño mediano ≤ 1,2·celda |
| `continua` | resto |

Salida de cada marca: `color` (hex), `style`, `components`, `bbox_m`, `points_m` (centros, máx. 200) y `segments_m` (extremos por eje principal, solo para continua y discontinua).

Las coordenadas de las marcas están en **metros desde la esquina inferior izquierda** del objeto en esa vista.

## `metric_dims(views, cells, cell_m)`

Combina todas las vistas con malla:

- **Ancho**: frente, detrás y (eje X de) arriba/abajo.
- **Alto**: frente, detrás, izquierda y derecha.
- **Fondo**: izquierda, derecha y (eje Y de) arriba/abajo.

Cada valor es la media; si el máximo y el mínimo difieren más del 6 % se añade un aviso. En el pipeline las dimensiones se normalizan con alto = 1: `dims = (ancho/alto, 1, fondo/alto)`, y la altura real en metros se guarda en `info.metric`.
