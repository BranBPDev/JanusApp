[⬅ README](../README.md)

# 🚀 Uso

> Aplicación de escritorio (Windows) que convierte **vistas 2D + mallas** en un **modelo 3D optimizado** que se abre, con LODs y GLB.

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
| `app/projects/` | Un directorio por objeto generado |
| `app/settings/` | Ajustes |

## ⚡ En 5 pasos

1. Abre la pestaña **Forma**.
2. Pulsa **Cargar vistas y mallas…** y elige todas las imágenes a la vez (se asignan por el nombre, ver [Vistas y mallas](vistas-y-mallas.md)).
3. Pulsa **Generar modelo 3D**.
4. Revisa el resultado en el visor.
5. **Abrir carpeta** lleva al proyecto guardado.

> [!IMPORTANT]
> Mínimo: vista **frontal** + una **lateral**, y **cada vista con su malla**.

## 🖥️ Pantallas

| Sección | Qué hace |
|---|---|
| 🏠 **Inicio** | Versión, fecha y autor. Lista de proyectos con **miniatura 3D**, triángulos, «se abre» y fecha. El **lápiz** de cada fila abre el proyecto en *Forma* para cambiar imágenes y regenerar |
| 🧊 **Forma** | Genera el objeto (ver abajo) |
| Texturas · Colisión · Esqueleto · Visor 3D | «Próximamente» |

**Forma**

| Panel izquierdo | Panel derecho |
|---|---|
| 6 tarjetas **Vista / Malla** (2×3) | Visor 3D |
| **Interior (opcional)**: *Tapa* y *Base* | Deslizador **Apertura** (si el objeto se abre) |
| Cargar · Generar · Nuevo proyecto | **LOD0–LOD3**, **Ver malla**, **Abrir carpeta** |
| Barra de progreso y estado | Información del modelo y avisos en amarillo |

**Visor**: arrastrar = rotar · rueda = zoom (0,3×–6×) · doble clic = restablecer.

## 🗂️ Archivos generados

```
app/projects/<nombre>/
├── manifest.json
├── views/        front.png left.png …      copias de las vistas
├── grids/        front.png left.png …      copias de las mallas
├── interiors/    movable.png fixed.png     (si se usaron)
└── shape/        lod0.glb … lod3.glb · lod0.obj · lod0.mtl · texture.png
```

| Caso | Qué se guarda |
|---|---|
| Esfera o elipsoide (con o sin salientes) | **Un** `lod0.glb` ya cortado + `lod0.obj` + `texture.png`; el descriptor paramétrico va en `manifest.json` |
| Primitiva (caja, cilindro…) o volumen | Un `.glb` por LOD + `lod0.obj/.mtl` + `texture.png` |

Un nombre de proyecto solo conserva letras, números, `_`, `-`, `.` y espacios (máx. 60). `shape/` se vacía y regenera en cada generación.

## ⚠️ Avisos habituales

- *Falta la malla de: …* · *No se detecta una cuadrícula regular en la malla …*
- *Las vistas no son del todo coherentes entre sí; el modelo puede perder detalle.*
- *Las mallas dan anchos/altos/fondos distintos según la vista.*
- *No se pudo abrir el objeto por la línea de corte marcada…*

Los errores quedan en `app/logs/janus.log`.
