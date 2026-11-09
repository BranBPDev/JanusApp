"""Vistas ortográficas de una «malla» del JSON (frente, detrás, izquierda, derecha, arriba, abajo): la vista previa de un objeto con
malla se dibuja desde la propia malla, con el color de cada zona, y no desde imágenes aparte."""
import numpy as np

from app.shape.zbuffer import visibility

# filas: dirección en el modelo de «derecha de la imagen», «arriba de la imagen» y «hacia el observador»
# (modelo: Y arriba, frente hacia +Z; en «izquierda» el frente queda a la izquierda de la imagen, como en el resto de vistas del formato)
AXES = {"frente": ((1, 0, 0), (0, 1, 0), (0, 0, 1)), "detras": ((-1, 0, 0), (0, 1, 0), (0, 0, -1)),
        "izquierda": ((0, 0, -1), (0, 1, 0), (1, 0, 0)), "derecha": ((0, 0, 1), (0, 1, 0), (-1, 0, 0)),
        "arriba": ((1, 0, 0), (0, 0, -1), (0, 1, 0)), "abajo": ((1, 0, 0), (0, 0, 1), (0, -1, 0))}
LIGHT = np.array([-0.4, 0.6, 0.7]) / np.linalg.norm([-0.4, 0.6, 0.7])    # respecto al observador (x derecha, y arriba, z hacia él)


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
    shade = 0.45 + 0.55 * np.clip(n[vis] @ LIGHT, 0, 1)
    colors = np.array(mesh["colors"], np.float64)[zones[vis]] * shade[:, None]
    scr = np.stack([(tri[vis, :, 0] - frame.ox) * frame.k, frame.h - (tri[vis, :, 1] - frame.oy) * frame.k], axis=2)
    _, ids = visibility(scr, tri[vis, :, 2], frame.w, frame.h)       # z-buffer: lo más cercano de cada píxel, sin depender del orden
    img = np.zeros((frame.h * frame.w, 3), np.float32)
    seen = ids >= 0
    img[seen] = np.clip(colors[ids[seen]], 0, 255)
    return img.reshape(frame.h, frame.w, 3), seen.reshape(frame.h, frame.w)
