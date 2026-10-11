[⬅ Volver al README](../../README.md)

# Preprocesado de siluetas (`preprocess.py`)

`load_silhouette(path)` convierte una imagen en una `View`.

## Pasos

1. Abre la imagen y la convierte a RGBA.
2. Si el lado mayor supera `MAX_SIDE = 768` px, la reduce (LANCZOS) guardando la escala.
3. **Máscara**:
   - Si más del 0,5 % de los píxeles tiene alfa < 0,5 → PNG con transparencia real: máscara = alfa ≥ 0,5.
   - Si no, se estima el fondo como la **mediana de los píxeles del borde** y se segmenta por distancia de color con un umbral de **Otsu** (mínimo 12).
4. `fill_holes`: rellena los huecos internos (fondo que no toca el borde de la imagen).
5. Calcula la cobertura. Si es > 0,92 o < 0,002, añade el aviso *"no se pudo separar el objeto del fondo (usa un PNG con transparencia)"*.
6. Recorta la máscara y la imagen a la caja del objeto. Si no hay ningún objeto lanza `ValueError("la imagen no contiene ningún objeto")`.

## `View`

| Campo | Significado |
|---|---|
| `mask` | Máscara booleana recortada |
| `rgba` | Imagen RGBA recortada |
| `warning` | Aviso o `None` |
| `scale` | Píxeles originales por píxel procesado |
| `box` | `(x0, y0, x1, y1)` del objeto en píxeles procesados |
| `original_size` | `(ancho, alto)` de la imagen original |

`scale` y `box` permiten pasar medidas de la malla (en píxeles originales) al sistema de la silueta. Ver [Escala métrica](escala-metrica.md).
