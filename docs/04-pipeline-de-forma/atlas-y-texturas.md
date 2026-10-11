[⬅ Volver al README](../../README.md)

# Atlas de texturas (`atlas.py`)

El objeto usa **una sola textura** que contiene las vistas colocadas como *charts* más unos bloques de color plano.

## Constantes

| Constante | Valor | Uso |
|---|---|---|
| `cap` | 256 | Tamaño máximo (px) del atlas antes de ajustar a potencia de 2 |
| `GAP` | 3 | Separación entre charts |
| `BLOCK` | 8 | Lado de los bloques de color plano |
| `NEUTRAL` | (205, 205, 210) | Gris neutro |

## Disposición

```
fila 1:  frente   | detrás
fila 2:  izquierda| derecha
fila 3:  arriba   | abajo     | [bloque móvil][bloque fijo][bloque base]
```

- Cada chart se escala para caber en `cap`; el tamaño final del atlas es la potencia de 2 siguiente (mínimo 32).
- `CHARTS` asocia cada vista con su dirección hacia la cámara.
- Antes de reescalar (LANCZOS) se aplica `extend_colors` a cada vista: extiende hasta 10 iteraciones el color del borde del objeto sobre el fondo para evitar halos oscuros al filtrar.

## Bloques de color plano

| Bloque | Uso | Color |
|---|---|---|
| 0 (`moving_uv`) | Interior de la pieza móvil | Mezcla del color medio de la pieza con el neutro |
| 1 (`fixed_uv`) | Interior de la pieza fija (y cuerpo sin corte) | Ídem |
| 2 | Cara inferior si no hay vista «abajo» | Media del 1/12 inferior de la vista frontal |

`paint_blocks` los repinta una vez conocidos los colores reales de las piezas (solo con el LOD0).

## UV por esquina (`corner_uvs`)

Cada cara exterior se asigna al chart de la vista que **mejor la ve** (mayor producto de la normal con la dirección de la vista). Las caras interiores van al bloque plano y las caras mirando hacia abajo sin vista inferior, al bloque 2. Los volteos detectados (`fl`, `fr`, `ft`, `fb`) se aplican en `_image_uv`.

## Texturas en objetos paramétricos

No usan atlas: se hornea una textura equirrectangular (ver [Primitivas](primitivas.md)).

> La resolución de textura está limitada a 256 px (`cap`). Aumentarla implica cambiar ese parámetro.
