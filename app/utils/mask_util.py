"""Operaciones sobre máscaras booleanas (2D o 3D): crecer, rellenar desde el borde, etiquetar... Las usan la IA y el modelado."""
from collections import deque

import numpy as np


def grow(m):
    """Máscara ampliada una celda en cada eje (vecinos que comparten cara)."""
    g = m.copy()
    for ax in range(m.ndim):
        lo, hi = [slice(None)] * m.ndim, [slice(None)] * m.ndim
        lo[ax], hi[ax] = slice(1, None), slice(None, -1)
        g[tuple(lo)] |= m[tuple(hi)]
        g[tuple(hi)] |= m[tuple(lo)]
    return g


def dilate(m, n=1):
    for _ in range(n):
        m = grow(m)
    return m


def erode(m, n=1):
    return ~dilate(~m, n)


def border(shape):
    """Máscara con solo el marco exterior de un array 2D."""
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


def label(mask, diagonal=False):
    """(etiquetas, cuántas): componentes conexas de una máscara 2D, numeradas por orden de aparición (de arriba abajo)."""
    h, w = mask.shape
    steps = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx) and (diagonal or not (dy and dx))]
    lab = np.zeros((h, w), np.int32)
    n = 0
    for y, x in zip(*np.nonzero(mask)):
        if lab[y, x]:
            continue
        n += 1
        lab[y, x] = n
        q = deque([(y, x)])
        while q:
            cy, cx = q.popleft()
            for dy, dx in steps:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                    lab[ny, nx] = n
                    q.append((ny, nx))
    return lab, n
