"""Objeto que ya es una malla 3d («malla» del JSON): se usa tal cual, con un color liso por zona y los LODs por simplificación."""
import numpy as np

from app.shape.geometry.qem import decimate

BLOCK = 8          # lado (px) de cada bloque de color de la textura


def zone_texture(colors):
    """Textura con un bloque de color liso por zona: (imagen RGBA uint8, UV del centro de cada bloque)."""
    n = len(colors)
    tex = np.full((BLOCK, BLOCK * n, 4), 255, np.uint8)
    for i, c in enumerate(colors):
        tex[:, i * BLOCK:(i + 1) * BLOCK, :3] = c
    uv = np.array([[(i * BLOCK + BLOCK / 2) / (BLOCK * n), 0.5] for i in range(n)])
    return tex, uv


def transfer_zones(V0, F0, zones0, V, F):
    """Zona de cada cara de la malla simplificada: la de la cara original más cercana (por centro)."""
    c0 = V0[F0].mean(axis=1)
    c = V[F].mean(axis=1)
    out = np.empty(len(F), zones0.dtype)
    for a in range(0, len(F), 512):
        d = ((c[a:a + 512, None, :] - c0[None, :, :]) ** 2).sum(-1)
        out[a:a + 512] = zones0[np.argmin(d, axis=1)]
    return out


def levels(V, F, zones, tolerances, progress=None):
    """[(V, F, zonas)] por LOD: el primero es la malla tal cual y cada siguiente se simplifica del anterior hasta su tolerancia (fracción del tamaño)."""
    size = float((V.max(axis=0) - V.min(axis=0)).max())
    out, cur = [(V, F, zones)], (V, F)
    for li, tol in enumerate(tolerances[1:], 1):
        cur = decimate(cur[0], cur[1], tol * size, 12)
        out.append((cur[0], cur[1], transfer_zones(V, F, zones, *cur)))
    return out
