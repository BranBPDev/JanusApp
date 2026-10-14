[⬅ README](../README.md)

# 🖼️ Vistas y mallas

La **vista** da el aspecto (color y textura); la **malla** da la escala real y dice **cómo es** el objeto: dónde se abre y qué sobresale.

## 👁️ Las seis vistas

| Vista | Clave | Palabras reconocidas en el nombre | Orientación |
|---|---|---|---|
| Frente | `front` | `front` `frente` `delante` `frontal` | cámara en +Z |
| Detrás | `back` | `back` `atras` `detras` `trasera` `posterior` `rear` | cámara en −Z |
| Izquierda | `left` | `left` `izq` | el frente mira a la izquierda |
| Derecha | `right` | `right` `der` | el frente mira a la derecha |
| Arriba | `top` | `top` `arriba` `superior` `cenital` | el frente queda **abajo** de la imagen |
| Abajo | `bottom` | `bottom` `abajo` `inferior` `debajo` | el frente queda **arriba** de la imagen |

Si una vista lateral o cenital está volteada, se detecta sola.

### 🏷️ Nombre de archivo

```
<objeto>_<vista>[_malla].png          starterball_frente.png · starterball_frente_malla.png
<objeto>_interior_<tapa|base>.png     starterball_interior_tapa.png · starterball_interior_base.png
```

- Sin tildes ni mayúsculas. El nombre del objeto (y del proyecto) es lo que sobra al quitar vista y `malla`.
- Formatos: `png` `jpg` `jpeg` `bmp` `webp` `tga` `tif` `tiff`.
- Lo ideal es **PNG con transparencia**; si no, el fondo se estima por el color del borde (debe ser liso).
- Todas las vistas, del **mismo objeto** y encuadradas ajustadas a él.

## 📐 La malla

Imagen del **mismo tamaño** que su vista con una cuadrícula regular: **cada cuadro = 0,05 m**.

- Las líneas ocupan al menos la mitad de la imagen y son regulares (tolera ±8 % y alguna línea ausente).
- Los cuadros deben ser cuadrados (si difieren más de un 5 % se avisa).
- Con las mallas de todas las vistas se miden ancho, alto y fondo; si dos vistas difieren más de un 6 % se avisa.

## 🎨 Marcas de color

Todo lo que se dibuje sobre la malla en un color distinto al de la cuadrícula es una **marca**.

| Color | Marca | Dónde | Obligatoria |
|---|---|---|---|
| 🔴 Rojo | **Línea de corte** (por aquí se abre) | Lateral (cualquier inclinación) o frente/detrás (horizontal) | Para que se abra |
| 🟢 Verde | **Punto** en la parte que se mueve | Derecha, izquierda, frente o detrás | No (por defecto, la de arriba) |
| 🔵 Azul | **Punto** en la bisagra, sobre el borde trasero de la esfera (donde se unen tapa y base) | Lateral | No (por defecto, el borde trasero del corte) |
| 🟡 Amarillo | **Círculo del botón**: queda **entero en la tapa** y deja su hueco en la base | Frente | No |
| 🟣 Violeta | **Contorno de un saliente** (tapa, cierre…) visto de frente | Vista que lo ve de cara | No |

<sub>Umbrales RGB: rojo `R>150 G<110 B<110` · verde `G>130 R<120 B<120` · azul `B>150 R<100 G<130` · amarillo `R>200 G>150 B<100` · violeta `R>130 G<110 B>150`.</sub>

### 🟣 Salientes

Cuando el cuerpo es redondo pero algo **sobresale** (la tapa superior, un cierre, un asa…), el contorno de las vistas ya lo muestra, pero no su forma en planta. Se la das dibujando su **contorno en violeta** en la malla de la vista que lo ve de cara:

| Saliente | Se dibuja en la malla de | Contorno |
|---|---|---|
| Tapa superior con cuatro soportes | **Arriba** | círculo de la tapa + un círculo por soporte |
| Cierre frontal | **Frente** | círculo que lo rodea (un poco mayor que el botón) |

La aplicación ajusta el cuerpo **ignorando** lo que sobresale, y genera aparte la malla de los salientes (altura sacada de las siluetas, forma de la marca). Se unen a la pieza correspondiente y viajan con ella al abrirse: lo que cae dentro del círculo del botón va con la **tapa**.

> [!TIP]
> Sin marcas violeta, todo lo que sobresale del cuerpo se reconstruye con el casco de las siluetas (los salientes salen más «cuadrados»).

## 📂 Texturas interiores (opcional)

Una imagen cuadrada por pieza, `…_interior_tapa` (pieza móvil) y `…_interior_base` (pieza fija). Se proyectan en plano sobre el interior mirando al corte: eje horizontal = X, vertical = profundidad (frente **abajo**). Un círculo inscrito coincide con el borde del corte. Solo se usan si el objeto se abre.

## ✅ Ejemplo: `starterball`

| Archivos | Contenido |
|---|---|
| `starterball_{frente,detras,izquierda,derecha,arriba,abajo}.png` | Vistas |
| `starterball_{…}_malla.png` | Mallas: corte rojo, bisagra azul (extremo trasero), botón amarillo en el frente, 🟣 círculo del cierre (frente) y 🟣 tapa + cuatro soportes (arriba) |
| `starterball_interior_{tapa,base}.png` | Interiores (la base con la «X» y el buje central) |

Resultado: esfera con tapa y cierre **sobresalientes**, que se abre como la Pokéball normal.
