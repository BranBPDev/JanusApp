"""Colores de una imagen de referencia: agrupación k-means y formato hexadecimal."""
import numpy as np


def _kmeans(px, k, iters=12):
    rng = np.random.default_rng(1)
    cent = px[rng.choice(len(px), k, replace=False)].astype(np.float64)
    for _ in range(iters):
        d = ((px[:, None, :] - cent[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            sel = px[lab == j]
            if len(sel):
                cent[j] = sel.mean(0)
    return cent, lab


def _hex(c):
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in c)
