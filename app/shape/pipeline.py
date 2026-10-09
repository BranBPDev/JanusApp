import time
from dataclasses import dataclass, field

import numpy as np

from app.shape.analysis import find_seam
from app.shape.atlas import Atlas
from app.shape.cut import OPEN_ANGLE, split_openable
from app.shape.field import compose, compute_dims, detect_orientation, grid_shape, make_arrays
from app.shape.mesh_ops import build_attributes, crease_normals, is_watertight, remove_small_components, taubin_smooth
from app.shape.model import Model, Part
from app.shape.preprocess import load_silhouette
from app.shape.primitive import fit_primitive, primitive_field
from app.shape.qem import decimate
from app.shape.surface_nets import surface_nets

VIEW_NAMES = {"front": "frente", "back": "detrás", "left": "izquierda", "right": "derecha", "top": "arriba"}
LOD_TOLERANCE = (0.015, 0.03, 0.06, 0.12)   # error medio admitido por nivel (fracción del tamaño del objeto)
RESOLUTION = 88
RESOLUTION_PRIMITIVE = 64
PAD = 2


@dataclass
class ShapeParams:
    """Lo único que decide el usuario: el tamaño. Todo lo demás se calcula a partir de las vistas."""
    height: float = 1.0   # alto en metros
    length: float = 0.0   # mayor dimensión horizontal en metros (0 = proporcional al alto)


@dataclass
class ShapeResult:
    lods: list
    warnings: list = field(default_factory=list)
    info: dict = field(default_factory=dict)


def _report(cb, frac, msg):
    if cb:
        cb(frac, msg)


def _mean_color(image, mask, rows):
    sel = np.zeros(mask.shape, bool)
    sel[rows] = True
    sel &= mask
    return image[..., :3][sel].mean(axis=0) if sel.any() else None


def generate_shape(view_paths: dict, params: ShapeParams, progress=None) -> ShapeResult:
    t0 = time.time()
    warnings = []

    masks, images = {}, {}
    given = {k: p for k, p in view_paths.items() if p}
    for i, (key, path) in enumerate(given.items()):
        _report(progress, 0.06 * i / len(given), f"Leyendo vista {VIEW_NAMES[key]}...")
        masks[key], images[key], warn = load_silhouette(path)
        if warn:
            warnings.append(f"Vista {VIEW_NAMES[key]}: {warn}.")
    if "front" not in masks or not ({"left", "right"} & set(masks)):
        raise ValueError("Se necesitan al menos la vista frontal y una vista lateral.")

    dims = compute_dims(masks)
    w, _, d = dims
    if "top" in masks and abs(masks["top"].shape[1] / masks["top"].shape[0] / (w / d) - 1) > 0.18:
        warnings.append("La vista superior no concuerda con las proporciones de las demás vistas.")

    # 1. Orientación de las vistas y forma: primitiva simple si explica las siluetas, si no volumen de las vistas
    _report(progress, 0.08, "Analizando la forma del objeto...")
    flips = {}
    if {"left", "right", "top"} & set(masks):
        flips, score = detect_orientation(masks, dims)
        if score < 0.9:
            warnings.append("Las vistas no son del todo coherentes entre sí; el modelo puede perder detalle.")
    low_shape, _ = grid_shape(dims, 40)
    primitive, iou = fit_primitive(make_arrays(masks, low_shape), low_shape, flips)
    shape, cell = grid_shape(dims, RESOLUTION_PRIMITIVE if primitive else RESOLUTION)

    if primitive:
        field_ = primitive_field(primitive, shape, PAD)
        smooth = 2
    else:
        vol, _ = compose(make_arrays(masks, shape), shape, **flips)
        field_ = np.pad(vol, PAD)
        smooth = 5

    _report(progress, 0.2, "Extrayendo superficie...")
    V, F = surface_nets(field_)
    if len(F) == 0:
        raise ValueError("No se pudo generar volumen. Revisa que las vistas correspondan al mismo objeto.")
    V, F = remove_small_components(V, F)
    V = taubin_smooth((V - PAD + 0.5) * cell, F, smooth)

    lo, hi = V.min(axis=0), V.max(axis=0)
    V = V - np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2])
    ext = hi - lo
    size_ref = float(ext.max())

    # 2. Simplificación guiada por error: cada nivel usa los menos triángulos posibles para su tolerancia
    levels, cur_v, cur_f = [], V, F
    for li, tol in enumerate(LOD_TOLERANCE):
        a, b = 0.3 + 0.35 * li / 4, 0.3 + 0.35 * (li + 1) / 4
        msg = f"Optimizando LOD{li}..."
        _report(progress, a, msg)
        cur_v, cur_f = decimate(cur_v, cur_f, tol * size_ref, 12,
                                lambda f, a=a, b=b, msg=msg: _report(progress, a + (b - a) * f, msg))
        levels.append((cur_v, cur_f))

    # 3. Color: atlas con las vistas + junta (si la hay) para dividir y vaciar el objeto
    _report(progress, 0.68, "Preparando textura...")
    seam = find_seam(images, masks)
    upper = lower = None
    if seam is not None:
        h = images["front"].shape[0]
        cut_row = int(round(seam * h))
        upper = _mean_color(images["front"], masks["front"], slice(0, cut_row))
        lower = _mean_color(images["front"], masks["front"], slice(cut_row, h))
    box_lo = np.array([-ext[0] / 2, 0.0, -ext[2] / 2])
    atlas = Atlas(images, masks, (box_lo, box_lo + ext), upper_color=upper, lower_color=lower)
    y_cut = float(ext[1] * (1 - seam)) if seam is not None else None

    _report(progress, 0.78, "Construyendo piezas...")
    sy = params.height / max(ext[1], 1e-9)
    sxz = params.length / max(ext[0], ext[2]) if params.length > 0 else sy
    lods, openable = [], False
    for (v, f), tol in zip(levels, LOD_TOLERANCE):
        parts, was_split = _build_parts(v, f, y_cut, atlas, min(2 * tol, 0.05) * size_ref)
        openable = openable or was_split
        lods.append(Model(parts, atlas.texture).scaled(sxz, sy))

    info = {
        "mode": "primitiva" if primitive else "volumen",
        "primitive": {"axis": primitive[0], "e1": primitive[1], "e2": primitive[2]} if primitive else None,
        "primitive_iou": round(float(iou), 4),
        "openable": openable, "seam": seam,
        "watertight": bool(is_watertight(levels[0][1])),
        "texture": [atlas.size[1], atlas.size[0]],
        "seconds": round(time.time() - t0, 2),
        "triangles": [m.triangles for m in lods],
        "size": [round(x, 4) for x in lods[0].size],
    }
    _report(progress, 0.92, "Modelo generado")
    return ShapeResult(lods=lods, warnings=warnings, info=info)


def _build_parts(V, F, y_cut, atlas, inner_tol):
    """Una pieza ('body') o, si hay junta y se puede cortar, base + tapa huecas con bisagra."""
    split = split_openable(V, F, y_cut, inner_tol) if y_cut is not None else None
    if split is None:
        specs = [("body", V, F, np.zeros(len(F), int), atlas.lower_uv, None)]
    else:
        (bv, bf, bk), (lv, lf, lk), hinge = split
        specs = [("base", bv, bf, bk, atlas.lower_uv, None), ("lid", lv, lf, lk, atlas.upper_uv, hinge)]

    parts = []
    for name, v, f, kind, interior_uv, hinge in specs:
        normals = crease_normals(v, f)
        uvs = atlas.corner_uvs(v, f, kind, interior_uv)
        verts, faces, nrm, uv = build_attributes(v, f, normals, uvs)
        extra = {"origin": hinge, "axis": (1.0, 0.0, 0.0), "open_angle": OPEN_ANGLE} if hinge else {}
        parts.append(Part(name, verts.astype(np.float32), faces, nrm.astype(np.float32), uv.astype(np.float32), **extra))
    return parts, split is not None
