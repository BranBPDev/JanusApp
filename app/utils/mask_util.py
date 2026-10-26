"""Operaciones sobre máscaras booleanas 2D (crecer, rellenar desde un borde...), compartidas por la IA y el modelado."""
import numpy as np


def grow(m):
    """Máscara ampliada un píxel (4 vecinos)."""
    g = m.copy()
    g[1:] |= m[:-1]
    g[:-1] |= m[1:]
    g[:, 1:] |= m[:, :-1]
    g[:, :-1] |= m[:, 1:]
    return g


def dilate(m, n=1):
    for _ in range(n):
        m = grow(m)
    return m


def erode(m, n=1):
    return ~dilate(~m, n)


def border(shape):
    """Máscara con solo el marco exterior."""
    b = np.zeros(shape, bool)
    b[0, :] = b[-1, :] = b[:, 0] = b[:, -1] = True
    return b


def flood(seed, free):
    """Parte de 'free' conectada con 'seed' (relleno por inundación)."""
    cur = seed & free
    for _ in range(sum(free.shape)):
        nxt = grow(cur) & free
        if (nxt == cur).all():
            break
        cur = nxt
    return cur
