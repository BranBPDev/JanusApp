"""Modelos 3D (.stl) como fuente de un objeto: se leen y se sacan las siluetas de las seis vistas con las que trabaja la aplicación.
Convención (la de Blender): Z hacia arriba, el objeto mira hacia -Y; X es el ancho. Las unidades del archivo no importan: la escala sale del alto pedido."""
import struct
from pathlib import Path

import numpy as np

from app.shape.spec.schema import SpecError

MODEL_EXT = {".stl"}
SIDE = 420                 # píxeles del lado mayor de cada silueta
POINTS = 2_500_000         # puntos que se reparten por la superficie para dibujar las siluetas


def load_stl(path) -> np.ndarray:
    """Triángulos (n, 3, 3) de un STL binario o ASCII."""
    data = Path(path).read_bytes()
    if len(data) >= 84:
        n = struct.unpack("<I", data[80:84])[0]
        if 84 + 50 * n == len(data):
            dt = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
            return np.frombuffer(data, dt, count=n, offset=84)["v"].astype(np.float64)
    try:
        words = data.decode("utf-8", "ignore").split()
        pts = [float(words[i + k]) for i, w in enumerate(words) if w == "vertex" for k in (1, 2, 3)]
    except (ValueError, IndexError):
        raise SpecError("No puedo leer el modelo 3d: no parece un STL válido.")
    if len(pts) < 9 or len(pts) % 9:
        raise SpecError("El STL no tiene triángulos.")
    return np.array(pts, np.float64).reshape(-1, 3, 3)


def _cover(mask, n=2):
    """Cierra los huecos de una silueta hecha de puntos: dilatar, rellenar lo cerrado y volver a erosionar."""
    def grow(m):
        g = m.copy()
        g[1:] |= m[:-1]
        g[:-1] |= m[1:]
        g[:, 1:] |= m[:, :-1]
        g[:, :-1] |= m[:, 1:]
        return g
    m = mask
    for _ in range(n):
        m = grow(m)
    # relleno: lo que no se alcanza desde el borde está dentro
    out = np.zeros_like(m)
    out[0, :] = out[-1, :] = out[:, 0] = out[:, -1] = True
    free = ~m
    out &= free
    for _ in range(sum(m.shape)):
        nxt = grow(out) & free
        if (nxt == out).all():
            break
        out = nxt
    m = ~out
    for _ in range(n):
        m = ~grow(~m)
    return m


def silhouettes(path):
    """({vista: máscara recortada}, (dx, dy, dz)) del modelo; todas las máscaras tienen la misma escala (píxeles por unidad del archivo)."""
    tri = load_stl(path)
    V = tri.reshape(-1, 3)
    lo, hi = V.min(0), V.max(0)
    ext = hi - lo
    if (ext <= 0).any():
        raise SpecError("El modelo 3d no tiene volumen.")
    rng = np.random.default_rng(7)
    area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    idx = rng.choice(len(tri), POINTS, p=area / area.sum())
    u, v = rng.random((POINTS, 1)), rng.random((POINTS, 1))
    flip = (u + v) > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    P = tri[idx, 0] + u * (tri[idx, 1] - tri[idx, 0]) + v * (tri[idx, 2] - tri[idx, 0])
    P = np.concatenate([P, V])
    s = SIDE / ext.max()
    Q = (P - lo) * s
    W, D, H = (int(np.ceil(e * s)) + 6 for e in ext)
    # (columna de la imagen, fila de la imagen, ancho, alto): fila 0 = arriba
    views = {"frente": (Q[:, 0], H - Q[:, 2], W, H), "detras": (W - Q[:, 0], H - Q[:, 2], W, H),
             "izquierda": (Q[:, 1], H - Q[:, 2], D, H), "derecha": (D - Q[:, 1], H - Q[:, 2], D, H),
             "arriba": (Q[:, 0], D - Q[:, 1], W, D), "abajo": (Q[:, 0], Q[:, 1], W, D)}
    out = {}
    for name, (cx, ry, w, h) in views.items():
        m = np.zeros((h, w), bool)
        m[np.clip(ry.astype(int) + 3, 0, h - 1), np.clip(cx.astype(int) + 3, 0, w - 1)] = True
        m = _cover(m)
        ys, xs = np.nonzero(m)
        out[name] = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return out, tuple(float(e) for e in ext)
