import numpy as np

from app.shape.atlas import CHARTS, NEUTRAL, extend_colors
from app.shape.cut import WALL, split_openable
from app.shape.mesh_ops import build_attributes, crease_normals
from app.shape.model import Model, Part
from app.shape.primitive import primitive_mesh
from app.shape.protrusion import assign_sides

TEX_WIDTH = 512
STRIP = 8          # filas extra con los colores planos del interior (si no hay texturas interiores)
MESH_GRID = (96, 48)   # (lados, anillos) de la esfera que se exporta


def is_ellipsoid(params) -> bool:
    return params is not None and params[1] == 1.0 and params[2] == 1.0


def bake_equirect(images, masks, ext, flips=None, width: int = TEX_WIDTH, frames=None):
    """Textura equirrectangular (u = longitud con el frente en 0,5; v = latitud con el polo +Y arriba) pintada con las vistas.
    'frames' = {vista: (cx, cy, rx, ry)} (fracciones de la imagen) con la elipse del cuerpo en cada vista; sin él el
    cuerpo ocupa toda la imagen."""
    f = flips or {}
    w, h = width, width // 2
    lon = ((np.arange(w) + 0.5) / w - 0.5) * 2 * np.pi
    lat = (0.5 - (np.arange(h) + 0.5) / h) * np.pi
    LON, LAT = np.meshgrid(lon, lat)
    d = np.stack([np.cos(LAT) * np.sin(LON), np.sin(LAT), np.cos(LAT) * np.cos(LON)], -1)
    half = np.asarray(ext, np.float64) / 2
    n = d / half
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    dx, dy, dz = d[..., 0], d[..., 1], d[..., 2]

    def frame(key):
        return (frames or {}).get(key, (0.5, 0.5, 0.5, 0.5))

    def uv(key):
        cx, cy, rx, ry = frame(key)
        if key == "front":
            return cx + dx * rx, cy - dy * ry
        if key == "back":
            return cx - dx * rx, cy - dy * ry
        if key == "right":
            return cx + (-dz if f.get("fr") else dz) * rx, cy - dy * ry
        if key == "left":
            return cx + (dz if f.get("fl") else -dz) * rx, cy - dy * ry
        if key == "top":
            return cx + dx * rx, cy + (-dz if f.get("ft") else dz) * ry
        return cx + dx * rx, cy + (dz if f.get("fb") else -dz) * ry

    acc = np.zeros((h, w, 3))
    total = np.zeros((h, w))
    for key, direction in CHARTS.items():
        if key not in images:
            continue
        img = extend_colors(images[key], masks[key])
        u, v = uv(key)
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


def _equirect_uvs(V, F, ext, center=None):
    half = np.asarray(ext, np.float64) / 2
    middle = np.array([0.0, half[1], 0.0]) if center is None else np.asarray(center, np.float64)
    rel = (V[F] - middle) / half
    norm = np.maximum(np.linalg.norm(rel, axis=2), 1e-9)
    u = np.arctan2(rel[..., 0], rel[..., 2]) / (2 * np.pi) + 0.5
    v = 0.5 - np.arcsin(np.clip(rel[..., 1] / norm, -1, 1)) / np.pi
    pole = (np.abs(rel[..., 0]) + np.abs(rel[..., 2])) < 1e-6
    free = ~pole
    big = np.where(free, u, -1.0).max(axis=1) - np.where(free, u, 2.0).min(axis=1) > 0.5   # cruza la costura
    u = np.where(big[:, None] & (u < 0.5) & free, u + 1.0, u)
    mean = (u * free).sum(axis=1) / np.maximum(free.sum(axis=1), 1)
    return np.stack([np.where(pole, mean[:, None], u), v], axis=2)


def _canvas(eq, atlas):
    """Textura exterior: la equirrectangular arriba y, debajo, el atlas de las vistas de los salientes."""
    h, w = eq.shape[:2]
    if atlas is None:
        return eq, (1.0, 1.0), None
    ah, aw = atlas.shape[:2]
    W, H = max(w, aw), h + ah
    out = np.full((H, W, 4), 255, np.uint8)
    out[:h, :w] = eq
    out[h:, :aw] = atlas
    return out, (w / W, h / H), (aw / W, ah / H, h / H)


def preview_model(ext, texture, opening, interior=None, center=None, extras=None):
    """Modelo de la esfera/elipsoide (vista previa y exportación). Devuelve (modelo, datos de apertura o None).
    'center' = centro del cuerpo si no está en el centro de la caja (objeto con salientes); 'extras' = malla de los
    salientes ({'V','F','uv','texture'}) que viaja con la pieza a la que pertenece."""
    h, w = texture.shape[:2]
    V, F = primitive_mesh((1, 1.0, 1.0), np.asarray(ext), *MESH_GRID)
    if center is not None:
        V = V + (np.asarray(center, np.float64) - np.array([0.0, ext[1] / 2, 0.0]))
    split = split_openable(V, F, opening) if opening else None
    if split is None:
        specs = [("body", V, F, np.zeros(len(F), int))]
    else:
        specs = [("fixed", *split[0]), ("movable", *split[1])]

    base_tex, core_scale, extras_rect = _canvas(texture, None if extras is None else extras["texture"])
    H, W = base_tex.shape[:2]
    side = None
    if extras is not None:
        moving = assign_sides(extras["V"], extras["F"], opening) if split is not None else np.zeros(len(extras["F"]), bool)
        side = {"movable": moving, "fixed": ~moving, "body": ~moving}
        eu, ev, eo = extras_rect
        euv = extras["uv"] * np.array([eu, ev]) + np.array([0.0, eo])

    raw, colors = [], {}
    for name, v, f, kind in specs:
        uvs = _equirect_uvs(v, f, ext, center)
        c = uvs[kind == 0].mean(axis=1)
        colors[name] = texture[np.clip((c[:, 1] * h).astype(int), 0, h - 1), (c[:, 0] % 1 * w).astype(int) % w, :3].mean(axis=0)
        uvs = uvs * np.array(core_scale)
        if extras is not None and side[name].any():          # los salientes se unen a la pieza (sin compartir vértices)
            sel = side[name]
            ef = extras["F"][sel]
            f = np.vstack([f, ef + len(v)])
            v = np.vstack([v, extras["V"]])
            kind = np.concatenate([kind, np.zeros(len(ef), int)])
            uvs = np.concatenate([uvs, euv[sel]])
        raw.append((name, v, f, kind, uvs))

    textured = split is not None and interior is not None and interior.any
    if textured:
        flat = {k: _interior(colors.get(k)) for k in ("movable", "fixed")}
        tex, (su, sv) = interior.attach(base_tex, flat)
        interior_uv = {k: interior.flat_uv(k) for k in ("movable", "fixed")}
        scale = np.array([su, sv])
    else:
        strip = np.full((STRIP, W, 4), 255, np.uint8)
        strip[:, : W // 2, :3] = _interior(colors.get("movable")).astype(np.uint8)
        strip[:, W // 2:, :3] = _interior(colors.get("fixed")).astype(np.uint8)
        tex = np.vstack([base_tex, strip])
        mid_v = (H + STRIP / 2) / (H + STRIP)
        interior_uv = {"movable": (0.25, mid_v), "fixed": (0.75, mid_v), "body": (0.75, mid_v)}
        scale = np.array([1.0, H / (H + STRIP)])

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


def descriptor(ext_m, opening_info=None, opening=None, scale=1.0, triangles=0, center_m=None, extras_triangles=0):
    """Descripción paramétrica de la esfera/elipsoide (el modelo ya cortado se exporta además como .glb).
    'center_m' = centro del cuerpo si no está en el centro de la caja; los salientes solo van en el .glb."""
    ax, ay, az = [float(v) / 2 for v in ext_m]
    out = {
        "type": "sphere" if max(ax, ay, az) / min(ax, ay, az) < 1.03 else "ellipsoid",
        "semi_axes": [round(ax, 5), round(ay, 5), round(az, 5)],
        "center": [0.0, round(ay, 5), 0.0] if center_m is None else [round(float(v), 5) for v in center_m],
        "texture": "texture.png",
        "uv": "equirect: u = atan2(x, z) / 2pi + 0.5 (frente en u=0.5); v = 0.5 - asin(y / semi_axis_y) / pi (origen arriba)",
        "triangles": triangles,
        "glb": "shape/lod0.glb",
    }
    if extras_triangles:
        out["extras"] = {"triangles": extras_triangles,
                         "note": "salientes (tapa, cierre...) fuera del cuerpo paramétrico: solo existen en el .glb"}
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
