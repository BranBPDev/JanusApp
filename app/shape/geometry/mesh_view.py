"""Vistas ortográficas de una «malla» del JSON (frente, detrás, izquierda, derecha, arriba, abajo): la vista previa de un objeto con
malla se dibuja desde la propia malla, con el color de cada zona, y no desde imágenes aparte."""
import numpy as np
from PIL import Image, ImageDraw

# filas: dirección en el modelo de «derecha de la imagen», «arriba de la imagen» y «hacia el observador»
# (modelo: Y arriba, frente hacia +Z; en «izquierda» el frente queda a la izquierda de la imagen, como en el resto de vistas del formato)
AXES = {"frente": ((1, 0, 0), (0, 1, 0), (0, 0, 1)), "detras": ((-1, 0, 0), (0, 1, 0), (0, 0, -1)),
        "izquierda": ((0, 0, -1), (0, 1, 0), (1, 0, 0)), "derecha": ((0, 0, 1), (0, 1, 0), (-1, 0, 0)),
        "arriba": ((1, 0, 0), (0, 0, -1), (0, 1, 0)), "abajo": ((1, 0, 0), (0, 0, 1), (0, -1, 0))}
LIGHT = np.array([-0.4, 0.6, 0.7]) / np.linalg.norm([-0.4, 0.6, 0.7])    # respecto al observador (x derecha, y arriba, z hacia él)


def bounds(mesh):
    """(ancho, alto, fondo) en metros de la caja de la malla."""
    V = mesh["vertices"]
    return tuple(float(v) for v in V.max(axis=0) - V.min(axis=0))


def draw_mesh(mesh, name, frame):
    """(rgb float (h, w, 3), silueta bool (h, w)) de la vista «name» dentro de «frame» (cuadro 0..ancho × 0..alto de esa vista)."""
    V, F, zones = mesh["vertices"], mesh["faces"], mesh["zones"]
    M = np.array(AXES[name], np.float64)
    P = V @ M.T                                                   # (x de la imagen, y de la imagen, cercanía)
    P[:, :2] -= P[:, :2].min(axis=0)
    tri = P[F]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    norm = np.linalg.norm(n, axis=1, keepdims=True)
    n = n / np.where(norm > 0, norm, 1)
    vis = np.nonzero((n[:, 2] > 0) & (norm[:, 0] > 0))[0]          # solo las caras que miran al observador
    order = vis[np.argsort(tri[vis, :, 2].mean(axis=1))]           # de lejos a cerca
    shade = 0.45 + 0.55 * np.clip(n[order] @ LIGHT, 0, 1)
    colors = np.array(mesh["colors"], np.float64)[zones[order]]
    px = (tri[order, :, 0] - frame.ox) * frame.k
    py = frame.h - (tri[order, :, 1] - frame.oy) * frame.k
    img = Image.new("RGB", (frame.w, frame.h), (0, 0, 0))
    sil = Image.new("L", (frame.w, frame.h), 0)
    d, ds = ImageDraw.Draw(img), ImageDraw.Draw(sil)
    for i in range(len(order)):
        poly = [(px[i, 0], py[i, 0]), (px[i, 1], py[i, 1]), (px[i, 2], py[i, 2])]
        d.polygon(poly, fill=tuple(int(c) for c in np.clip(colors[i] * shade[i], 0, 255)))
        ds.polygon(poly, fill=255)
    return np.asarray(img, np.float32), np.asarray(sil) > 127
