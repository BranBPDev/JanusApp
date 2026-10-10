import numpy as np

from app.shape.atlas import CHARTS, extend_colors
from app.shape.mesh_ops import build_attributes, crease_normals
from app.shape.model import Model, Part
from app.shape.primitive import primitive_mesh

TEX_WIDTH = 256
PREVIEW_GRID = (32, 16)


def is_ellipsoid(params) -> bool:
    return params is not None and params[1] == 1.0 and params[2] == 1.0


def bake_equirect(images, masks, ext, width: int = TEX_WIDTH):
    """Textura equirrectangular (u = longitud con el frente en 0,5; v = latitud con el polo +Y arriba) pintada con las vistas."""
    w, h = width, width // 2
    lon = ((np.arange(w) + 0.5) / w - 0.5) * 2 * np.pi
    lat = (0.5 - (np.arange(h) + 0.5) / h) * np.pi
    LON, LAT = np.meshgrid(lon, lat)
    d = np.stack([np.cos(LAT) * np.sin(LON), np.sin(LAT), np.cos(LAT) * np.cos(LON)], -1)
    half = np.asarray(ext, np.float64) / 2
    n = d / half
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    t = (d * half + np.array([0.0, half[1], 0.0]) - np.array([-half[0], 0.0, -half[2]])) / np.asarray(ext)
    x, y, z = t[..., 0], t[..., 1], t[..., 2]
    coords = {"front": (x, 1 - y), "back": (1 - x, 1 - y), "right": (z, 1 - y), "left": (1 - z, 1 - y), "top": (x, z)}

    acc = np.zeros((h, w, 3))
    total = np.zeros((h, w))
    for key, direction in CHARTS.items():
        if key not in images:
            continue
        img = extend_colors(images[key], masks[key])
        u, v = coords[key]
        ih, iw = img.shape[:2]
        inside = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
        px = img[np.clip((v * ih).astype(int), 0, ih - 1), np.clip((u * iw).astype(int), 0, iw - 1), :3].astype(np.float64)
        wgt = np.clip(n @ np.array(direction, np.float64), 0, 1) ** 4 * inside
        acc += px * wgt[..., None]
        total += wgt
    tex = np.full((h, w, 4), 255, np.uint8)
    tex[..., :3] = np.clip(acc / np.maximum(total[..., None], 1e-6), 0, 255).astype(np.uint8)
    return tex


def _equirect_uvs(V, F, ext):
    half = np.asarray(ext, np.float64) / 2
    rel = (V[F] - np.array([0.0, half[1], 0.0])) / half
    norm = np.maximum(np.linalg.norm(rel, axis=2), 1e-9)
    u = np.arctan2(rel[..., 0], rel[..., 2]) / (2 * np.pi) + 0.5
    v = 0.5 - np.arcsin(np.clip(rel[..., 1] / norm, -1, 1)) / np.pi
    pole = (np.abs(rel[..., 0]) + np.abs(rel[..., 2])) < 1e-6
    free = ~pole
    big = np.where(free, u, -1.0).max(axis=1) - np.where(free, u, 2.0).min(axis=1) > 0.5   # cruza la costura
    u = np.where(big[:, None] & (u < 0.5) & free, u + 1.0, u)
    mean = (u * free).sum(axis=1) / np.maximum(free.sum(axis=1), 1)
    return np.stack([np.where(pole, mean[:, None], u), v], axis=2)


def preview_model(ext, texture):
    """Malla SOLO para la vista previa de la aplicación (no se exporta)."""
    V, F = primitive_mesh((1, 1.0, 1.0), np.asarray(ext), *PREVIEW_GRID)
    verts, faces, nrm, uv = build_attributes(V, F, crease_normals(V, F, 60.0), _equirect_uvs(V, F, ext))
    return Model([Part("body", verts.astype(np.float32), faces, nrm.astype(np.float32), uv.astype(np.float32))], texture)


def descriptor(ext_m):
    """Lo único que se guarda del objeto: esfera/elipsoide paramétrico y su textura. Sin triángulos."""
    ax, ay, az = [float(v) / 2 for v in ext_m]
    return {
        "type": "sphere" if max(ax, ay, az) / min(ax, ay, az) < 1.03 else "ellipsoid",
        "semi_axes": [round(ax, 5), round(ay, 5), round(az, 5)],
        "center": [0.0, round(ay, 5), 0.0],
        "texture": "texture.png",
        "uv": "equirect: u = atan2(x, z) / 2pi + 0.5 (frente en u=0.5); v = 0.5 - asin(y / semi_axis_y) / pi (origen arriba)",
        "triangles": 0,
    }
