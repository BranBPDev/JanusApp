[⬅ Volver al README](../../README.md)

# Preparar las vistas

## Las seis vistas

| Clave interna | Título en la app | Palabras reconocidas en el nombre del archivo |
|---|---|---|
| `front` | Frente | `front`, `frente`, `delante`, `frontal` |
| `back` | Detrás | `back`, `atras`, `detras`, `trasera`, `posterior`, `rear` |
| `left` | Izquierda | `left`, `izq` |
| `right` | Derecha | `right`, `der` |
| `top` | Arriba | `top`, `arriba`, `superior`, `cenital` |
| `bottom` | Abajo | `bottom`, `abajo`, `inferior`, `debajo` |

La comparación ignora mayúsculas y tildes. Las vistas izquierda/derecha se comprueban primero para evitar confusiones con otras palabras.

## Nombre del archivo

`<objeto>_<vista>[_malla].png`

- `pokeball_frente.png` → vista frontal de `pokeball`.
- `pokeball_frente_malla.png` → su malla (se detecta por las palabras `malla`, `grid` o `mesh`).

El nombre del objeto (y de la carpeta del proyecto) es lo que queda del nombre del primer archivo al quitar la vista y la palabra de malla. Si no queda nada, se usa `objeto`.

## Formatos admitidos

`.png`, `.jpg`, `.jpeg`, `.bmp`, `.webp`, `.tga`, `.tif`, `.tiff`

## Requisitos de las imágenes

- **Fondo**: lo ideal es un PNG con transparencia. Si no la tiene, el fondo se estima por el color de los bordes (debe ser uniforme).
- Si el objeto no se puede separar del fondo (cubre más del 92 % o menos del 0,2 % de la imagen) aparece un aviso.
- Las imágenes mayores de 768 px de lado se reducen internamente; la escala se conserva para las medidas.
- Todas las vistas deben corresponder **al mismo objeto** y estar encuadradas ajustadas a él.

## Orientación de las vistas

Convención por defecto:

- **Frente**: cámara en +Z. **Detrás**: cámara en −Z.
- **Derecha**: el frente del objeto mira hacia la derecha de la imagen. **Izquierda**: hacia la izquierda.
- **Arriba**: el frente del objeto está en la parte inferior de la imagen. **Abajo**: en la parte superior.

Si alguna vista lateral o cenital está volteada, la aplicación lo detecta automáticamente (ver [Orientación y volumen](../04-pipeline-de-forma/orientacion-y-volumen.md)).

## Asignación manual

Cada casilla tiene un botón verde **+** (elegir imagen), una papelera roja (quitar) y admite arrastrar y soltar un archivo.

Siguiente: [Mallas y marcas de apertura](mallas-y-marcas.md)
