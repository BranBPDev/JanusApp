[⬅ Volver al README](../../README.md)

# Visor 3D por software (`viewer.py`, `render.py`)

El visor no usa OpenGL: dibuja los triángulos con `QPainter` ordenados por profundidad (algoritmo del pintor). Es ligero y funciona sin aceleración gráfica.

## Controles

| Acción | Efecto |
|---|---|
| Arrastrar con el ratón | Rotar (`yaw` / `pitch`; el `pitch` se limita a ±1,5 rad) |
| Rueda | Zoom entre 0,3× y 6× |
| Doble clic | Restablecer la vista |
| Deslizador «Apertura» | Abre/cierra el objeto (0–100 %) |
| «Ver malla» | Dibuja el contorno de los triángulos |

Vista inicial: `yaw = 0,5`, `pitch = 0,25`, `zoom = 1`.

## `Scene` (`render.py`, sin Qt)

Calcula lo que dibuja el visor:

- `posed(t)`: vértices y normales con apertura `t` (0 cerrado, 1 abierto), aplicando la rotación de cada pieza móvil (fórmula de Rodrigues, `rotation`) alrededor de su pivote y recorriendo la jerarquía de `parent`.
- Encuadre: centro y radio calculados con el objeto cerrado y abierto.
- `draw_list(yaw, pitch, zoom, t, ancho, alto)`:
  1. Rota, descarta caras traseras y ordena de lejos a cerca.
  2. Sombreado `0,4 + 0,6 · max(0, n·luz)` con luz fija `(-0,4; 0,6; 0,7)`.
  3. Calcula la transformación afín textura→pantalla por triángulo.
  4. Agranda cada triángulo ~0,7 px para evitar rendijas.
- Las caras interiores y los bordes (UV constante) reciben un sesgo de profundidad de `-0,02·radio` para que el orden no las deje pasar al frente.

## `MeshViewer`

Para cada triángulo texturizado se asigna la textura como `QBrush` con su transformación y se superpone un velo negro con alfa `(1 − sombra)·255`. Los triángulos sin textura se rellenan con su color plano sombreado.

> En objetos paramétricos el visor muestra una malla de vista previa que no se guarda.
