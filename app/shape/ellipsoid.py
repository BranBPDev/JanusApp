import numpy as np

from app.shape.atlas import CHARTS, NEUTRAL, extend_colors
from app.shape.cut import WALL, split_openable
from app.shape.mesh_ops import build_attributes, crease_normals
from app.shape.model import Model, Part
from app.shape.primitive import primitive_mesh

TEX_WIDTH = 512
STRIP = 8          # filas extra con los colores planos del interior (si no hay texturas interiores)
MESH_GRID = (96, 48)   # (lados, anillos) de la esfera que se exporta


def is_ellipsoid(params) -> bool:
    return params is not None and params[1] == 1.0 and params[2] == 1.0


def bake_equirect(images, masks, ext, flips=None, width: int = TEX_WIDTH):
    """Textura equirrectangular (u = longitud con el frente en 0,5; v = latitud con el polo +Y arriba) pintada con las vistas."""
    f = flips or {}
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
    coords = {"front": (x, 1 - y), "back": (1 - x, 1 - y),
              "right": (1 - z if f.get("fr") else z, 1 - y), "left": (z if f.get("fl") else 1 - z, 1 - y),
              "top": (x, 1 - z if f.get("ft") else z), "bottom": (x, z if f.get("fb") else 1 - z)}

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


def _interior(mean):
    mean = NEUTRAL if mean is None else np.asarray(mean, np.float64)
    return np.clip(0.25 * mean + 0.75 * NEUTRAL, 0, 255)


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


def preview_model(ext, texture, opening, interior=None):
    """Modelo de la esfera/elipsoide (vista previa y exportación). Devuelve (modelo, datos de apertura o None)."""
    h, w = texture.shape[:2]
    V, F = primitive_mesh((1, 1.0, 1.0), np.asarray(ext), *MESH_GRID)
    split = split_openable(V, F, opening) if opening else None
    if split is None:
        specs = [("body", V, F, np.zeros(len(F), int))]
    else:
        specs = [("fixed", *split[0]), ("movable", *split[1])]

    raw, colors = [], {}
    for name, v, f, kind in specs:
        uvs = _equirect_uvs(v, f, ext)
        c = uvs[kind == 0].mean(axis=1)
        colors[name] = texture[np.clip((c[:, 1] * h).astype(int), 0, h - 1), (c[:, 0] % 1 * w).astype(int) % w, :3].mean(axis=0)
        raw.append((name, v, f, kind, uvs))

    textured = split is not None and interior is not None and interior.any
    if textured:
        flat = {k: _interior(colors.get(k)) for k in ("movable", "fixed")}
        tex, (su, sv) = interior.attach(texture, flat)
        interior_uv = {k: interior.flat_uv(k) for k in ("movable", "fixed")}
        scale = np.array([su, sv])
    else:
        strip = np.full((STRIP, w, 4), 255, np.uint8)
        strip[:, : w // 2, :3] = _interior(colors.get("movable")).astype(np.uint8)
        strip[:, w // 2:, :3] = _interior(colors.get("fixed")).astype(np.uint8)
        tex = np.vstack([texture, strip])
        mid_v = (h + STRIP / 2) / (h + STRIP)
        interior_uv = {"movable": (0.25, mid_v), "fixed": (0.75, mid_v), "body": (0.75, mid_v)}
        scale = np.array([1.0, h / (h + STRIP)])

    parts = []
    for name, v, f, kind, uvs in raw:
        uvs = uvs * scale
        uvs[kind == 1] = np.array(interior_uv[name])
        if textured and name in ("movable", "fixed"):
            uvs = interior.remap(uvs, kind, v, f, name, opening["normal"], opening["point"], (ext[0], ext[2]))
        verts, faces, nrm, uv = build_attributes(v, f, crease_normals(v, f, 60.0), uvs)
        extra = {}
        if name == "movable":
            extra = {"origin": split[2], "axis": split[3], "open_angle": split[4]}
        parts.append(Part(name, verts.astype(np.float32), faces, nrm.astype(np.float32), uv.astype(np.float32), **extra))
    info = None
    if split is not None:
        info = {"hinge": split[2], "axis": split[3], "angle": split[4], "colors": colors,
                "interior_textures": interior.used() if textured else {"movable": False, "fixed": False},
                "uv_scale": [float(scale[0]), float(scale[1])]}
    return Model(parts, tex), info


def descriptor(ext_m, opening_info=None, opening=None, scale=1.0, triangles=0):
    """Descripción paramétrica de la esfera/elipsoide (el modelo ya cortado se exporta además como .glb)."""
    ax, ay, az = [float(v) / 2 for v in ext_m]
    out = {
        "type": "sphere" if max(ax, ay, az) / min(ax, ay, az) < 1.03 else "ellipsoid",
        "semi_axes": [round(ax, 5), round(ay, 5), round(az, 5)],
        "center": [0.0, round(ay, 5), 0.0],
        "texture": "texture.png",
        "uv": "equirect: u = atan2(x, z) / 2pi + 0.5 (frente en u=0.5); v = 0.5 - asin(y / semi_axis_y) / pi (origen arriba)",
        "triangles": triangles,
        "glb": "shape/lod0.glb",
    }
    if opening_info is not None:
        r = lambda a: [round(float(x) * scale, 5) for x in a]
        out["opening"] = {
            "plane_point": r(opening["point"]),
            "plane_normal": [round(float(x), 5) for x in opening["normal"]],
            "moving_side": "la del lado al que apunta plane_normal",
            "hinge": r(opening_info["hinge"]),
            "axis": list(opening_info["axis"]),
            "open_angle_deg": opening_info["angle"],
            "wall": WALL,
            "interior_textures": opening_info.get("interior_textures"),
            "interior_texture_projection": "plana sobre el corte: u = x / ancho + 0.5, v = z / fondo + 0.5 (frente abajo); cada pieza tiene su celda cuadrada bajo la textura exterior",
            "exterior_uv_scale": opening_info.get("uv_scale"),
            "button": None if not opening.get("button") else {
                "center_xy": r(opening["button"]["center"]),
                "radius": round(float(opening["button"]["radius"]) * scale, 5),
                "note": "disco en la cara frontal (z > 0): pertenece entero a la parte móvil y deja su hueco en la fija",
            },
            "interior_color": {k: np.round(_interior(v)).astype(int).tolist() for k, v in opening_info["colors"].items()},
        }
    return out
