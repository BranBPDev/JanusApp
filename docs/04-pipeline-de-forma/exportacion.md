[⬅ Volver al README](../../README.md)

# Exportación (`export.py`, `project.py`)

## `texture_png(textura)`

Codifica un array RGBA `uint8` como PNG optimizado y devuelve los bytes.

## OBJ + MTL (`write_obj`)

- Pose de reposo (cerrado), un grupo `g` por pieza.
- Incluye `v`, `vt` (con `v` invertida porque OBJ tiene el origen abajo), `vn` y caras `f v/vt/vn`.
- El `.mtl` define el material `janus` (`Kd 1 1 1`) y `map_Kd texture.png` si hay textura.
- Solo se escribe para el LOD0.

## GLB (`write_glb`)

glTF 2.0 binario construido a mano (sin librerías externas):

- Una **malla por pieza**, con `POSITION` (relativa al pivote), `NORMAL`, `TEXCOORD_0` e índices `u16` o `u32` según el tamaño.
- Jerarquía de nodos: nodo raíz con el nombre del objeto; cada pieza cuelga de su `parent` (o de la raíz) con `translation` relativa a los pivotes.
- Las piezas móviles llevan `extras.janus = { axis, open_angle_deg }`.
- Un único material PBR (`baseColorTexture`, metálico 0, rugosidad 0,5) y la textura PNG embebida.
- Cabecera, trozo JSON (relleno con espacios) y trozo BIN alineados a 4 bytes.

## `save_shape` (`project.py`)

1. Crea `views/`, `grids/` y `shape/` en `app/projects/<nombre>/` y copia las imágenes originales con la clave de la vista como nombre.
2. Vacía `shape/`.
3. **Paramétrico**: guarda solo `texture.png`.
   **Con malla**: un GLB por LOD, `lod0.obj`/`lod0.mtl` y `texture.png`.
4. Lee el `manifest.json` previo (si existe) para conservar las fases.
5. Escribe el manifest (ver [Formato de manifest.json](../07-referencia/manifest-json.md)).

`PHASES = ("shape", "texture", "collision", "rig")`: tras generar, `shape` = true y `texture` = true si hay textura; el resto conserva su valor anterior.

`sanitize_name(nombre)`: sustituye por `_` lo que no sea `\w`, `-`, `.` o espacio, recorta espacios y puntos de los extremos y limita a 60 caracteres.
