[⬅ Volver al README](../../README.md)

# Apertura del objeto (`opening.py`, `cut.py`)

## 1. Interpretar las marcas (`opening.find_opening`)

Entrada: marcas de las mallas, dimensiones en metros y altura. Salida: `{point, normal, hinge}` en unidades del modelo (alto = 1) y avisos.

`role(color)` clasifica cada marca: `corte` (rojo), `mueve` (verde) o `bisagra` (azul).

**Plano de corte**

1. Se busca el segmento rojo más largo en las vistas `right` o `left`: da un plano con cualquier inclinación (la normal se orienta hacia arriba / hacia delante).
2. Si no hay, se busca en `front` o `back` un segmento horizontal (pendiente ≤ 10 %): plano horizontal.
3. Si hay marcas rojas pero no se pueden interpretar, se avisa.

**Parte móvil**: el primer punto verde (en `right`, `left`, `front` o `back`) decide el lado; la normal pasa a apuntar hacia él.

**Bisagra**: el primer punto azul de `right` o `left`. Si no hay, se usa el borde trasero del corte.

`_to_world` convierte coordenadas de marca (metros desde la esquina inferior izquierda de cada vista) a coordenadas del mundo.

## 2. Cortar la malla (`cut.split_openable`)

1. `_cut`: corta los triángulos por el plano. Los vértices sobre el plano se reutilizan; el resto de aristas se parten una sola vez.
2. `_single_loop`: el corte debe formar **un único contorno cerrado**; si no (o hay menos de 4 caras por lado) devuelve `None` y el objeto no se abre.
3. `_hollow`: vacía cada mitad con una cúpula interior de pocos triángulos (borde, un anillo intermedio y un ápice), con las caras mirando al hueco. Cada pieza es `(V, F, kind)` con `kind` 0 = exterior y 1 = interior.
4. `_angle`: elige el signo de giro que aleja la pieza móvil del resto.

Constantes: `WALL = 0,93` (profundidad relativa del interior), `OPEN_ANGLE = 75°`, eje fijo `X = (1, 0, 0)`.

## Resultado

Se devuelven `(fija, móvil, bisagra, eje, ángulo)`. La pieza `movable` lleva `origin` (bisagra), `axis` y `open_angle`, y `parent` queda sin definir en las piezas actuales (ambas son raíz).

Los colores planos del interior se calculan como `0,25 · color medio de la pieza + 0,75 · gris neutro` (`NEUTRAL = 205, 205, 210`).

Cómo se dibuja la apertura: [Visor 3D](visor.md). Cómo se marca: [Mallas y marcas](../02-guia-de-usuario/mallas-y-marcas.md).
