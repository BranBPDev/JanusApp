import numpy as np


def texels(tex, u, v):
    """Texel (RGBA) más cercano a cada coordenada UV (origen arriba; fuera de [0, 1] se queda en el borde)."""
    h, w = tex.shape[:2]
    return tex[np.clip((np.asarray(v) * h).astype(int), 0, h - 1), np.clip((np.asarray(u) * w).astype(int), 0, w - 1)]


def face_texels(tex, uvs, faces):
    """Texel del centro de cada triángulo; 'uvs' = UV por vértice (n, 2) o por esquina (m, 3, 2) si 'faces' es None."""
    c = (uvs if faces is None else uvs[faces]).mean(axis=1)
    return texels(tex, c[:, 0], c[:, 1])
