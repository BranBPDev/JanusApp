[⬅ Volver al README](../../README.md)

# Archivos generados (proyectos)

Cada objeto se guarda en `app/projects/<nombre>/` (junto al `.exe`). El nombre se sanea: los caracteres que no sean letras, números, `_`, `-`, `.` o espacio se sustituyen por `_` y se limita a 60 caracteres.

## Estructura

```
app/projects/<nombre>/
├── manifest.json
├── views/
│   ├── front.png
│   └── left.png ...
├── grids/
│   ├── front.png
│   └── left.png ...
└── shape/
    ├── lod0.glb  lod1.glb  lod2.glb  lod3.glb
    ├── lod0.obj
    ├── lod0.mtl
    └── texture.png
```

- `views/` y `grids/`: copias de las imágenes originales, renombradas con la clave de la vista.
- `shape/` se **vacía y se regenera** en cada generación.

## Objetos con malla

- Un `.glb` (glTF 2.0 binario) por LOD, con una malla por pieza, jerarquía de nodos y pivotes, y una sola textura/material.
- `lod0.obj` + `lod0.mtl` en pose de reposo, con un grupo por pieza.
- `texture.png` compartida por todos los niveles.

## Objetos paramétricos (esfera/elipsoide)

Solo se guarda `shape/texture.png`. La descripción del objeto (tipo, semiejes, UV equirrectangular y apertura) va dentro de `manifest.json`, en `shape.primitive_object`. No se escribe ninguna malla: el motor que use el objeto debe aportar su esfera/elipsoide compartida.

## manifest.json

Resume el proyecto: vistas, mallas, marcas leídas, resultado de la forma y estado de las fases. Estructura completa en [Formato de manifest.json](../07-referencia/manifest-json.md).

Si el manifest ya existía, se conserva el estado de las demás fases.

Detalles técnicos de los formatos: [Exportación](../04-pipeline-de-forma/exportacion.md).
