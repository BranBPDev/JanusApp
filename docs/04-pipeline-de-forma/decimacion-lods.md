[⬅ Volver al README](../../README.md)

# Decimación y LODs (`qem.py`)

## Algoritmo

`decimate(V, F, max_error, min_faces=24, progress=None, locked=None, return_map=False)` simplifica con **colapso de aristas y error cuádrico** (Garland-Heckbert).

1. `_vertex_quadrics`: matriz cuádrica por vértice (suma ponderada por área de los planos de sus caras).
2. Cada arista se mete en un montículo con su coste y la posición óptima de colapso (`_best`: solución del sistema 3×3 si es estable y cercana, si no el mejor entre los dos extremos y el punto medio; más una pequeña penalización por longitud, `eps = 1e-3`).
3. Se extrae la de menor coste y se colapsa si:
   - su coste no supera `max_error²` (en caso contrario termina);
   - no deja geometría no-manifold (vecinos comunes = caras compartidas);
   - ningún triángulo vecino se da la vuelta (normal con coseno < 0,1).
4. Se actualizan versiones, cuádricas y aristas vecinas.
5. Se detiene al llegar a `min_faces` (12 en el pipeline) o cuando el siguiente colapso supera el error.

`locked` impide mover o eliminar vértices (solo se puede colapsar sobre el vértice fijo). `return_map=True` devuelve además la correspondencia de índices.

## Niveles de detalle (volumen reconstruido)

| LOD | Error medio admitido (fracción del tamaño del objeto) |
|---|---|
| 0 | 0,02 |
| 1 | 0,04 |
| 2 | 0,08 |
| 3 | 0,15 |

Cada nivel parte del resultado del anterior (decimación progresiva).

## LODs de primitivas

No se decimó desde el volumen: cada LOD es una malla nueva con menos lados y anillos (ver [Primitivas](primitivas.md)).

## Objetos paramétricos

Un solo «nivel» (la malla de vista previa); los botones LOD se desactivan.

> El algoritmo está escrito en Python puro (listas y conjuntos), por lo que es la parte más lenta del pipeline en mallas grandes.
