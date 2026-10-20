"""Relieves del JSON: piezas que sobresalen de un cuerpo esférico y siguen su curvatura (franjas, por ahora).

Una «franja» es la zona de la esfera que queda a menos de ancho/2 de un círculo máximo inclinado, elevada 'sobresale_m'
sobre la superficie. Se calcula en coordenadas de la caja del objeto (metros): x = ancho, y = alto (suelo en 0) y
z = fondo (el frente es z = fondo), y de ahí salen tanto la silueta de cada vista como la malla del modelo."""
import math
from dataclasses import dataclass

import numpy as np

KINDS = ("franja",)
DEFAULTS = {"inclinacion_grados": 45.0, "ancho_m": 0.04, "sobresale_m": 0.01, "margen_m": 0.05, "simetrica": True}
EMBED = 0.003        # lo que se hunde la base de la pieza dentro del cuerpo para que no quede rendija
ALONG, ACROSS = 64, 9


@dataclass
class ReliefMesh:
    V: np.ndarray        # (n, 3) metros, coordenadas de la caja
    F: np.ndarray        # (m, 3) caras con la normal hacia fuera
    color: tuple         # RGB 0-255 liso
    center: np.ndarray = None   # centro y radio de la esfera de la que sobresale (para saber qué tapa el cuerpo)
    radius: float = 0.0


def flat_color(texture):
    """Color liso que representa una textura (la de color, el principio del degradado o el tono claro de la veta)."""
    for key in ("color", "desde", "claro"):
        if key in texture:
            return tuple(int(c) for c in texture[key])
    return (128, 128, 128)


def _strip(center, radius, tilt, width, rise, margin, side):
    t = math.radians(tilt)
    a = np.array([side * math.cos(t), math.sin(t), 0.0])          # dirección del círculo máximo más alta
    z = np.array([0.0, 0.0, 1.0])
    n = np.cross(a, z)                                            # normal del plano del círculo
    delta = (width / 2) / radius
    mr = margin / radius
    gam = np.linspace(-delta, delta, ACROSS)
    grid = np.zeros((ACROSS, ALONG + 1, 3))
    for j, g in enumerate(gam):
        q = (mr - math.sin(g) * n[1]) / (math.cos(g) * a[1])      # cos(beta) mínimo para estar sobre el margen
        if q >= 1.0:
            raise ValueError("La franja no cabe: el margen es mayor que su altura. Reduce «margen_m» o la inclinación.")
        bmax = math.acos(max(q, -1.0))
        b = np.linspace(-bmax, bmax, ALONG + 1)
        grid[j] = math.cos(g) * (np.cos(b)[:, None] * a + np.sin(b)[:, None] * z) + math.sin(g) * n
    top = center + (radius + rise) * grid            # superficie exterior; 'grid' son las normales (esfera)
    base = center + (radius - EMBED) * grid
    V = np.concatenate([top.reshape(-1, 3), base.reshape(-1, 3)])
    nb = ACROSS * (ALONG + 1)
    ix = lambda j, i: j * (ALONG + 1) + i
    F, centroid_dir = [], []
    for j in range(ACROSS - 1):
        for i in range(ALONG):
            a_, b_, c_, d_ = ix(j, i), ix(j, i + 1), ix(j + 1, i + 1), ix(j + 1, i)
            F += [(a_, b_, c_), (a_, c_, d_)]
    F = np.array(F, np.int64)
    out = np.einsum("ij,ij->i", np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), V[F].mean(axis=1) - center)
    F[out < 0] = F[out < 0][:, ::-1]
    walls = []

    def side_wall(pairs, inner_of):
        for (p, q_), inner in zip(pairs, inner_of):
            mid = (V[p] + V[q_]) / 2
            quad = [(p, q_, q_ + nb), (p, q_ + nb, p + nb)]
            for tri in quad:
                nrm = np.cross(V[tri[1]] - V[tri[0]], V[tri[2]] - V[tri[0]])
                walls.append(tri if nrm @ (mid - V[inner]) > 0 else tri[::-1])

    last = ALONG
    pairs, inner = [], []
    for i in range(ALONG):                                         # borde de abajo (j=0) y de arriba (j=último)
        pairs.append((ix(0, i), ix(0, i + 1))); inner.append(ix(1, i))
        pairs.append((ix(ACROSS - 1, i), ix(ACROSS - 1, i + 1))); inner.append(ix(ACROSS - 2, i))
    for j in range(ACROSS - 1):                                    # extremos (i=0 e i=último)
        pairs.append((ix(j, 0), ix(j + 1, 0))); inner.append(ix(j, 1))
        pairs.append((ix(j, last), ix(j + 1, last))); inner.append(ix(j, last - 1))
    side_wall(pairs, inner)
    return V, np.concatenate([F, np.array(walls, np.int64)])


def build_reliefs(items, textures, dims):
    """Mallas (en la caja del objeto) de todos los relieves del JSON. 'dims' = (ancho, alto, fondo)."""
    out = []
    for item in items:
        p = {**DEFAULTS, **item}
        radius = float(p["radio_m"])
        center = np.array([dims[0] / 2, radius, dims[2] / 2])
        sides = (1, -1) if p["simetrica"] else (1,)
        for side in sides:
            V, F = _strip(center, radius, float(p["inclinacion_grados"]), float(p["ancho_m"]), float(p["sobresale_m"]),
                          float(p["margen_m"]), side)
            out.append(ReliefMesh(V, F, flat_color(textures[p["textura"]]), center, radius))
    return out


def view_points(key, V, dims):
    """Coordenadas (x, y) en metros de la vista 'key' de los puntos V (caja) y su profundidad (mayor = más cerca de la cámara)."""
    w, h, d = dims
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    table = {"front": (x, y, z), "back": (w - x, y, d - z), "right": (z, y, x), "left": (d - z, y, w - x),
             "top": (x, d - z, y), "bottom": (x, z, h - y)}
    a, b, depth = table[key]
    return np.stack([a, b], 1), depth


FACING = {"front": (2, 1), "back": (2, -1), "right": (0, 1), "left": (0, -1), "top": (1, 1), "bottom": (1, -1)}


def visible_faces(mesh, key):
    """Caras de un relieve que miran hacia la cámara de esa vista y no quedan tapadas por el cuerpo esférico."""
    axis, sign = FACING[key]
    V, F = mesh.V, mesh.F
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    ok = sign * n[:, axis] > 0
    if mesh.center is not None:
        rel = V[F].mean(axis=1) - mesh.center
        toward = sign * rel[:, axis]                       # >0: el punto está del lado de la cámara
        lateral = np.sqrt(np.maximum((rel ** 2).sum(axis=1) - toward ** 2, 0.0))
        ok &= (toward > 0) | (lateral > mesh.radius * 0.995)
    return ok


def to_extras(meshes, dims_m, height_m):
    """Salientes en el formato del modelo ({'V','F','uv','texture'}): alto = 1, centrado en x y z, el frente a +z.
    La textura es una fila de celdas lisas, una por relieve."""
    if not meshes:
        return None
    w, h, d = dims_m
    Vs, Fs, uvs, offset = [], [], [], 0
    texture = np.full((4, 4 * len(meshes), 4), 255, np.uint8)
    for k, m in enumerate(meshes):
        Vs.append(np.stack([(m.V[:, 0] - w / 2), m.V[:, 1], (m.V[:, 2] - d / 2)], 1) / height_m)
        Fs.append(m.F + offset)
        offset += len(m.V)
        texture[:, 4 * k:4 * k + 4, :3] = m.color
        uvs.append(np.broadcast_to(np.array([(k + 0.5) / len(meshes), 0.5]), (len(m.F), 3, 2)))
    return {"V": np.concatenate(Vs), "F": np.concatenate(Fs).astype(np.int32), "uv": np.concatenate(uvs), "texture": texture}
