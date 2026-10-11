[⬅ Volver al README](../../README.md)

# Generar el modelo 3D

## Pantalla «Forma»

**Panel izquierdo**

- Cuadrícula de 6 tarjetas (2 columnas × 3 filas), una por vista, cada una con su casilla **Vista** y su casilla **Malla**.
- **Cargar vistas y mallas...**: selección múltiple; asigna por nombre. Los archivos no reconocidos se listan como *"Sin asignar"*.
- **Generar modelo 3D**: lanza el proceso en segundo plano.
- Barra de progreso y línea de estado.

**Panel derecho**

- Visor 3D.
- Deslizador **Apertura** (solo si el objeto se abre).
- Botones **LOD0–LOD3**, casilla **Ver malla** (wireframe) y **Abrir carpeta**.
- Información del modelo y avisos (en amarillo).

## Validaciones antes de generar

- Debe haber vista **frontal** y al menos una **lateral**.
- Toda vista cargada debe tener su **malla** (*"Falta la malla de: ..."*).

## Qué se genera según la forma

| Caso | Resultado |
|---|---|
| Las siluetas encajan en una **esfera o elipsoide** | Objeto **paramétrico**: 0 triángulos propios, solo textura + descriptor. El visor muestra una malla de vista previa que **no se guarda**. Solo hay un nivel. |
| Encajan en otra **primitiva** (caja, cilindro, cápsula...) | Malla regular de la primitiva en 4 LODs |
| Ninguna primitiva las explica | **Volumen** reconstruido de las vistas, simplificado en 4 LODs |

Detalles en [Primitivas y elipsoides](../04-pipeline-de-forma/primitivas.md) y [Pipeline completo](../04-pipeline-de-forma/pipeline.md).

## Panel de información

Para objetos con malla: `LODn: triángulos · vértices · ancho × alto × fondo m · textura · forma · se abre · piezas`.

Para objetos paramétricos: tipo (esfera/elipsoide), tamaño, textura y aviso de que la malla del visor es solo una vista previa.

## Avisos habituales

- *Las vistas no son del todo coherentes entre sí; el modelo puede perder detalle.* (coherencia < 0,9)
- *La vista X no concuerda con las proporciones de las demás vistas.* (arriba/abajo, desviación > 18 %)
- *Las mallas dan anchos/altos/fondos distintos según la vista.*
- *Vista X: no se pudo separar el objeto del fondo (usa un PNG con transparencia).*

## Errores

Se muestran en la línea de estado como `Error: ...` y quedan registrados en `app/logs/janus.log`.

Siguiente: [Archivos generados](archivos-generados.md)
