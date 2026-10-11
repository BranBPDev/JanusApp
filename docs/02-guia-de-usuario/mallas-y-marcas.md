[⬅ Volver al README](../../README.md)

# Mallas y marcas de apertura

Cada vista se acompaña de una **malla**: una imagen del mismo tamaño con una cuadrícula regular dibujada. De ella se saca la **escala real** del objeto y las **marcas** que indican por dónde se abre.

## La cuadrícula

- Cada cuadro mide **siempre 0,05 m** (5 cm).
- Las líneas deben ocupar al menos la mitad del lado de la imagen.
- Las líneas deben ser regulares (tolerancia del 8 % entre separaciones; se admite que falte alguna).
- Los cuadros deben ser cuadrados (si difieren más del 5 % se avisa).
- La malla puede tener transparencia o ir sobre un fondo liso.
- Si no tiene el tamaño de la imagen se reescala (con aviso).
- Si no se detecta una cuadrícula regular, la generación falla con el mensaje *"No se detecta una cuadrícula regular en la malla ..."*.

Con las mallas de todas las vistas se calculan ancho, alto y fondo en metros. Si dos vistas dan medidas que difieren más de un 6 %, aparece un aviso. Detalle técnico: [Escala métrica](../04-pipeline-de-forma/escala-metrica.md).

## Marcas de color (apertura)

Todo lo que se dibuje sobre la malla en un color distinto al de la cuadrícula se interpreta como una **marca**.

| Color | Significado | Obligatoria |
|---|---|---|
| 🔴 Rojo | **Línea de corte**: por aquí se abre el objeto (tapa, boca, puerta...) | Sí, para que se abra |
| 🟢 Verde | **Punto** dentro de la parte que se mueve | No (por defecto, la parte de arriba del corte) |
| 🔵 Azul | **Punto** en la bisagra | No (por defecto, el borde trasero del corte) |

Umbrales de color (RGB): rojo `R>150, G<110, B<110`; verde `G>130, R<120, B<120`; azul `B>150, R<100, G<130`.

## Cómo dibujar el corte

Hay dos formas válidas:

1. **Línea roja en una vista lateral** (derecha o izquierda), con cualquier inclinación. Es la más flexible.
2. **Línea roja horizontal en la vista frontal o trasera**, que define un plano horizontal. Si está inclinada se avisa y se pide dibujarla también en una vista lateral.

Estilos de trazo admitidos (se detectan solos): continua, discontinua y puntos. Los puntos solo sirven para las marcas verde y azul.

## Dónde dibujar los puntos

- **Verde** (parte móvil): en cualquiera de las vistas derecha, izquierda, frente o detrás.
- **Azul** (bisagra): en una vista **lateral** (derecha o izquierda).

## Resultado

Si la marca es válida y el corte da una sola sección, el objeto se divide en dos piezas huecas, **fija** y **móvil**, unidas por una bisagra con eje X y 75° de apertura (el sentido se elige solo, hacia el lado que aleja la pieza). Ver [Apertura del objeto](../04-pipeline-de-forma/apertura.md).

Si no se puede abrir, se muestra el aviso *"No se pudo abrir el objeto por la línea de corte marcada..."* y el objeto se genera de una sola pieza.

Siguiente: [Generar el modelo 3D](generar-modelo.md)
