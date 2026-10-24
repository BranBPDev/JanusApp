[⬅ README](../README.md)

# 🧩 Objeto JSON (`janus.objeto/1`)

Un único archivo describe el objeto entero. Lo escribe la IA del chat, se puede editar a mano y se guarda con el proyecto (`source/objeto.json`). **Todas las medidas van en metros.**

```json
{
  "formato": "janus.objeto/1",
  "nombre": "pokeball",
  "medidas_m": {"ancho": 0.2, "alto": 0.2, "fondo": 0.2},
  "texturas": { "rojo": {"color": "#d62d20"} },
  "sombreado": {"luz": [-0.45, 0.6, 0.65], "base": 0.66, "intensidad": 0.4},
  "contorno": {"color": "#1c1c22", "grosor_m": 0.0015},
  "vistas": { "frente": {"capas": [ {"textura": "rojo", "forma": "circulo", "centro": [0.1, 0.1], "radio": 0.1, "silueta": true, "sombrear": true} ]} },
  "relieves": [],
  "marcas": {},
  "interior": {}
}
```

| Clave | Obligatoria | Qué es |
|---|---|---|
| `formato` | Sí | Siempre `"janus.objeto/1"` |
| `medidas_m` | Sí | `ancho` (X), `alto` (Y), `fondo` (Z) del objeto completo |
| `texturas` | Sí | Materiales con nombre |
| `vistas` | Sí | Cómo se ve cada vista: **`frente` y una lateral** como mínimo |
| `sombreado` · `contorno` | No | Luz respecto a la cámara · línea alrededor de la silueta de cada vista |
| `relieves` | No | Piezas que sobresalen de un cuerpo esférico |
| `marcas` | No | Corte, bisagra, botón, salientes y huesos |
| `interior` | No | Texturas de dentro de la tapa y de la base |

## 🎨 Texturas

| Forma | Ejemplo |
|---|---|
| Color | `{"color": "#d62d20"}` |
| Degradado | `{"degradado": {"desde": "#ffffff", "hasta": "#3070e0", "angulo": 90}}` (90° = de abajo a arriba; `"tipo": "radial"` = del centro al borde) |
| Veta | `{"veta": {"claro": "#eecd9c", "oscuro": "#cda472", "escala_m": 0.012, "semilla": 3}}` |

## 👁️ Vistas y capas

Vistas: `frente`, `detras`, `izquierda`, `derecha`, `arriba`, `abajo`. Coordenadas **como en la imagen, con el origen abajo a la izquierda** del cuadro que ocupa el objeto en esa vista:

| Vista | `x` | `y` |
|---|---|---|
| `frente` · `detras` | ancho | alto |
| `derecha` (el frente mira a la derecha) · `izquierda` | fondo | alto |
| `arriba` (el frente queda abajo) · `abajo` | ancho | fondo |

Cada vista es una lista `capas` que se dibuja **en orden**:

| `forma` | Campos |
|---|---|
| `circulo` | `centro`, `radio` |
| `elipse` | `centro`, `radios` `[rx, ry]` |
| `rect` | `esquina`, `tamano` `[ancho, alto]`, `radio_esquina` |
| `poligono` | `puntos` |
| `linea` | `puntos`, `grosor` |

Opciones de capa: `textura` (obligatoria), `silueta: true` (forma parte de la silueta; lo demás solo se pinta dentro de ella; **cada vista necesita al menos una**), `recorte` `[x0, y0, x1, y1]`, `borde` `{color, grosor_m}`, `sombrear: true` (círculo/elipse sombreado como una esfera) y `tallado`.

### 🪨 `tallado`

```json
{"textura": "triskel", "forma": "linea", "puntos": [[0.1, 0.1], [0.12, 0.13]], "grosor": 0.01,
 "tallado": {"tipo": "grabado", "profundidad": 0.7, "ancho_m": 0.0035, "grano": "piedra"}}
```

Efecto de talla en la textura: `tipo` `grabado` (hundido) o `relieve` (abultado), `profundidad` (0–1), `ancho_m` (suavizado del borde), `grano` `piedra` o `madera` (opcional). **Conserva los colores**: solo modula el brillo con bordes redondeados y sombra en la arista según `sombreado.luz`. Para que parezca tallado «en» la superficie, usa en la textura de la capa el mismo color que la superficie.

## 🔵 Relieves

Piezas que siguen la curvatura de una esfera centrada en la caja y apoyada en el suelo. Todos llevan `tipo`, `textura` y `radio_m` (radio de la esfera).

| `tipo` | Qué es | Campos principales |
|---|---|---|
| `franja` | Banda curva en relieve | `inclinacion_grados`, `ancho_m`, `sobresale_m`, `margen_m`, `simetrica` |
| `cadena` | Anillo de eslabones | `eje`, `radio_aro_m`, `eslabones`, `largo_m`, `ancho_m`, `grosor_m`, `hueco` |
| `cuerda` | Cuerda trenzada | `eje`, `radio_aro_m`, `hebras`, `vueltas`, `grosor_m`, `hueco` |
| `pieza` | Esfera, elipsoide, caja, cilindro, cono o toro | `forma`, `lat_grados`, `lon_grados`, `tamano_m` `[este, norte, altura]`, `giro_grados`, `hunde_m`, `copias`, `paso_grados` |
| `trazo` | Línea en relieve (p. ej. un símbolo) | `curvas` (listas de puntos `[x, y]`), `ancho_m`, `sobresale_m`, `copias`, `paso_grados`, `lat_grados`, `lon_grados` |
| `malla` | Pieza propia | `vertices` `[este, norte, fuera]`, `caras` `[i, j, k]` |

`hueco` = `{"eje": [x, y, z], "radio_m": r}` deja sin eslabones el entorno de ese punto de la esfera (p. ej. el botón). `lat_grados`/`lon_grados` dicen dónde va la pieza (`lon 0` = frente; `lat 90` = polo de arriba).

## 📍 Marcas

| Marca | Campos | Para qué |
|---|---|---|
| `corte` | `vista`, `linea` `[[x, y], [x, y]]` | Por aquí se abre el objeto |
| `mueve` | `vista`, `punto` | (opcional) lado que se mueve; por defecto, el de arriba |
| `bisagra` | `vista`, `punto` | (opcional) pivote; por defecto, el borde trasero del corte |
| `boton` | `vista`, `centro`, `radio` | Queda entero en la tapa y deja su hueco en la base |
| `salientes` | `vista`, una forma (`circulo`, `elipse`…) | Huella de lo que sobresale del cuerpo |
| `huesos` | `id` (0–59), `padre` (`null` = raíz), y un punto `[x, y]` por vista (`frente`, `derecha`…) | Esqueleto |

## 🔓 Interior

`interior.tapa` e `interior.base`: `{"lado_m": 0.2, "circular": true, "capas": [ … ]}` con las mismas capas. Se proyectan en plano sobre el interior mirando al corte. Solo se usan si el objeto se abre.

## ✅ Mínimo y plantillas

El mínimo válido es `medidas_m` + `texturas` + `vistas.frente` + una vista lateral, cada una con una capa de `silueta`. El chat parte de dos plantillas: *esfera simple* y *esfera con banda y botón* (que se abre e incluye el interior por defecto).

> [!TIP]
> Los objetos de forma libre se hacen con **polígonos** en cada vista: la silueta de cada vista fija el volumen y los polígonos de color la pintan. Es lo que genera la IA a partir de imágenes ([IA integrada](ia.md#️-objetos-a-partir-de-imágenes-y-archivos)).
