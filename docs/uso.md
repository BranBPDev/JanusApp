[⬅ README](../README.md)

# 🚀 Uso

> Aplicación de escritorio (Windows). Describes el objeto en un chat (o cargas su JSON) y la aplicación genera un **modelo 3D optimizado** que se abre, con LODs y GLB. La IA va **dentro del `.exe`**: no usa internet, no descarga nada y no consume tokens.

## 📦 Instalación

1. Descarga `JanusApp.zip` de la [última release](https://github.com/BranBPDev/JanusApp/releases/latest).
2. Descomprímelo donde quieras y ejecuta `JanusApp.exe` (no hace falta Python).

```
JanusApp.exe
app/data/version.json
```

Junto al `.exe` se crea `app/` con los datos del usuario, que **una actualización nunca borra**:

| Carpeta | Contenido |
|---|---|
| `app/logs/` | `janus.log` (rotativo) |
| `app/logs/ia/` | `peticiones.jsonl`: lo que pides a la IA y lo que responde (sirve para reentrenarla) |
| `app/projects/` | Un directorio por objeto generado |
| `app/settings/` | Ajustes |

## ⚡ En 4 pasos

1. Abre la pestaña **Forma**.
2. Escribe en el chat qué objeto quieres (o adjunta imágenes / un JSON).
3. Mira la **vista previa** que aparece en la respuesta y sigue pidiendo cambios.
4. Pulsa **Generar modelo 3D** (botón dentro de la respuesta) y revisa el resultado en el visor.

**Abrir carpeta** lleva al proyecto guardado; **Guardar JSON** guarda el objeto tal cual está.

## 💬 El chat

| Elemento | Qué hace |
|---|---|
| Cuadro de texto | Enter envía · Shift+Enter, salto de línea |
| **Adjuntar** (o arrastrar al chat) | Imágenes (PNG, JPG, JFIF, WEBP, BMP, GIF, TIF, TGA, SVG) y un JSON de objeto |
| **Deshacer** | Vuelve al objeto anterior (hasta 30 pasos) |
| **Nuevo** | Vacía el objeto y la conversación |
| **Bien / Mal** | Valora la respuesta; con «Mal» puedes escribir qué querías. Queda en el registro de la IA |
| Chips de ejemplo | Peticiones de muestra con un clic |

Ejemplos de lo que se le puede pedir:

```
Hazme una esfera con banda y botón, arriba roja y abajo blanca, con la banda negra
Cambia la banda por una cuerda roja y añade un triskel arriba
Ahora el triskel tallado en piedra, hacia adentro        (el tallado conserva el color de la tapa)
Hazme la starterball
Hazme a <nombre>, te paso imágenes     (con «frente» y «lateral» en el nombre de los archivos)
Hazla el doble de grande · Quita los adornos · Pon la tapa verde oscuro
```

Más detalle en [IA integrada](ia.md).

## 🖥️ Pantallas

| Sección | Qué hace |
|---|---|
| 🏠 **Inicio** | Versión, fecha y autor. Lista de proyectos con **miniatura 3D**, triángulos, «se abre» y fecha. El **lápiz** de cada fila abre el proyecto en *Forma* con su JSON para seguir editándolo |
| 🧊 **Forma** | Chat con la IA + visor 3D (ver abajo) |
| Texturas · Colisión · Esqueleto · Visor 3D | «Próximamente» |

**Forma**

| Panel izquierdo (chat) | Panel derecho |
|---|---|
| Conversación con vista previa y botón **Generar modelo 3D** en cada respuesta | Visor 3D |
| Adjuntar · Deshacer · Nuevo · Enviar | Deslizador **Apertura** (si el objeto se abre) · **Mover** y **Ver huesos** (si tiene esqueleto) |
| Estado de la IA | **LOD0–LOD3**, **Ver malla**, **Abrir carpeta**, información del modelo y avisos en amarillo |

**Visor**: arrastrar = rotar · rueda = zoom · doble clic = restablecer.

## 🗂️ Archivos generados

```
app/projects/<nombre>/
├── manifest.json
├── source/objeto.json      el JSON del objeto: lo único que hace falta para regenerarlo
└── shape/                  lod0.glb … lod3.glb · lod0.obj · lod0.mtl · texture.png
```

| Caso | Qué se guarda |
|---|---|
| Esfera o elipsoide (con o sin salientes y relieves) | **Un** `lod0.glb` ya cortado + `lod0.obj` + `texture.png`; el descriptor paramétrico va en `manifest.json` |
| Primitiva (caja, cilindro…) o volumen | Un `.glb` por LOD + `lod0.obj/.mtl` + `texture.png` |

Un nombre de proyecto solo conserva letras, números, `_`, `-`, `.` y espacios (máx. 60). `shape/` se vacía y regenera en cada generación.

## ⚠️ Avisos habituales

- *Todavía no hay ningún objeto: pídeme primero uno…* · *Eso no lo puedo construir con mis piezas… adjunta imágenes…*
- *No estoy del todo seguro de haberte entendido…* (la IA no tiene confianza; revisa la vista previa).
- *<archivo>: no dice qué vista es…* (nombra las imágenes con «frente», «lateral», «detras», «arriba»…).
- *Las vistas no son del todo coherentes entre sí; el modelo puede perder detalle.*
- *La silueta de la vista … se sale del cuadro de «medidas_m»…*
- *No se pudo abrir el objeto por la línea de corte marcada…*

Los errores quedan en `app/logs/janus.log`.
