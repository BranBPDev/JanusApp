[⬅ Volver al README](../../README.md)

# Glosario

| Término | Significado |
|---|---|
| **Vista** | Imagen 2D del objeto desde una de las seis direcciones (frente, detrás, izquierda, derecha, arriba, abajo) |
| **Malla** | Imagen con una cuadrícula de 5 cm por cuadro que da la escala real; también lleva las marcas de apertura. *No* es una malla 3D |
| **Marca** | Dibujo de color sobre la malla (rojo corte, verde parte móvil, azul bisagra) |
| **Silueta / máscara** | Región ocupada por el objeto en una vista |
| **Casco visual** | Volumen 3D obtenido intersectando las siluetas proyectadas |
| **Surface Nets** | Algoritmo que extrae una superficie triangulada de un campo escalar 3D |
| **Taubin** | Suavizado de malla que evita el encogimiento |
| **Supercuádrico** | Forma paramétrica con exponentes que va de la caja al elipsoide |
| **IoU** | Intersección sobre unión; mide cuánto coinciden dos siluetas |
| **Elipsoide / esfera paramétrica** | Objeto guardado solo como descriptor y textura, sin triángulos |
| **QEM** | Error cuádrico; método de simplificación de mallas (Garland-Heckbert) |
| **LOD** | *Level of Detail*; versión de la malla con menos triángulos (LOD0 = la más detallada) |
| **Atlas** | Textura única que agrupa las vistas como *charts* |
| **Chart** | Región del atlas dedicada a una vista |
| **UV** | Coordenadas de textura de un vértice |
| **Pieza fija / móvil** | Las dos mitades de un objeto que se abre |
| **Bisagra** | Punto de pivote de la pieza móvil; el eje de giro es X |
| **GLB** | glTF 2.0 en formato binario |
| **Fase** | Etapa de la cadena de trabajo: forma, texturas, colisión, esqueleto |
| **Frozen** | Ejecutándose desde el `.exe` de PyInstaller (`IS_FROZEN`) |
| **Staging** | Carpeta temporal (`temp_download/payload`) con la actualización descomprimida |
