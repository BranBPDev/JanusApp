import time
from dataclasses import dataclass, field

import numpy as np

from app.shape.atlas import Atlas
from app.shape.ellipsoid import bake_equirect, descriptor, is_ellipsoid, preview_model
from app.shape.field import compose, compute_dims, detect_orientation, grid_shape, make_arrays
from app.shape.mesh_ops import build_attributes, crease_normals, is_watertight, remove_small_components, taubin_smooth
from app.shape.metric import analyze_overlay, metric_dims
from app.shape.model import Model, Part
from app.shape.preprocess import load_silhouette
from app.shape.primitive import fit_primitive, is_round, primitive_mesh
from app.shape.qem import decimate
from app.shape.surface_nets import surface_nets

VIEW_NAMES = {"front": "frente", "back": "detrás", "left": "izquierda", "right": "derecha", "top": "arriba"}
LOD_TOLERANCE = (0.02, 0.04, 0.08, 0.15)   # error medio admitido por nivel (fracción del tamaño del objeto)
PRIMITIVE_GRID_ROUND = ((12, 6), (8, 4), (6, 2), (4, 2))   # (lados, anillos) por nivel
PRIMITIVE_GRID_SHARP = ((16, 8), (12, 6), (8, 4), (8, 4))
SHARP_CLEANUP = (0.03, 0.03, 0.05, 0.05)   # une las caras planas redundantes de cajas y cilindros
RESOLUTION = 88
PAD = 2


@dataclass
class ShapeParams:
    size: float = 1.0    # mayor dimensión en metros; solo se usa si no hay mallas (con malla el tamaño sale de la malla)
    cell: float = 0.1    # metros que mide cada cuadro de la malla


@dataclass
class ShapeResult:
    lods: list
    warnings: list = field(default_factory=list)
    info: dict = field(default_factory=dict)
    descriptor: dict = None   # objeto paramétrico (esfera/elipsoide): no se guarda ninguna malla
    texture: object = None    # textura que acompaña al descriptor
    marks: dict = field(default_factory=dict)   # marcas de las mallas por vista (para fases futuras)


def _report(cb, frac, msg):
    if cb:
        cb(frac, msg)


def generate_shape(view_paths: dict, grid_paths: dict, params: ShapeParams, progress=None) -> ShapeResult:
    t0 = time.time()
    warnings = []

    views = {}
    given = {k: p for k, p in view_paths.items() if p}
    for i, (key, path) in enumerate(given.items()):
        _report(progress, 0.06 * i / len(given), f"Leyendo vista {VIEW_NAMES[key]}...")
        views[key] = load_silhouette(path)
        if views[key].warning:
            warnings.append(f"Vista {VIEW_NAMES[key]}: {views[key].warning}.")
    if "front" not in views or not ({"left", "right"} & set(views)):
        raise ValueError("Se necesitan al menos la vista frontal y una vista lateral.")
    masks = {k: v.mask for k, v in views.items()}
    images = {k: v.rgba for k, v in views.items()}

    # Mallas: escala exacta y marcas
    cells, marks = {}, {}
    for key, path in (grid_paths or {}).items():
        if not path or key not in views:
            continue
        v = views[key]
        sx = v.scale
        x0, y0, x1, y1 = v.box
        found = analyze_overlay(path, v.original_size, (x0 * sx, y0 * sx, x1 * sx, y1 * sx), params.cell)
        if found is None:
            warnings.append(f"Malla {VIEW_NAMES[key]}: no se detecta una cuadrícula regular; se ignora.")
            continue
        if found["warning"]:
            warnings.append(f"Malla {VIEW_NAMES[key]}: {found['warning'].strip()}.")
        cells[key] = found["cell_px"]
        marks[key] = found["marks"]

    dims = compute_dims(masks)
    metric = None
    if cells:
        (mw, mh, md), metric_warnings = metric_dims(views, cells, params.cell)
        warnings += metric_warnings
        if mw and mh and md:
            dims = (mw / mh, 1.0, md / mh)
        metric = {"cell_m": params.cell, "height_m": mh, "width_m": mw, "depth_m": md}
    w, _, d = dims
    if "top" in masks and abs(masks["top"].shape[1] / masks["top"].shape[0] / (w / d) - 1) > 0.18:
        warnings.append("La vista superior no concuerda con las proporciones de las demás vistas.")

    # Orientación de las vistas y forma: primitiva simple si explica las siluetas, si no volumen de las vistas
    _report(progress, 0.08, "Analizando la forma del objeto...")
    flips = {}
    if {"left", "right", "top"} & set(masks):
        flips, score = detect_orientation(masks, dims)
        if score < 0.9:
            warnings.append("Las vistas no son del todo coherentes entre sí; el modelo puede perder detalle.")
    low_shape, _ = grid_shape(dims, 40)
    primitive, iou = fit_primitive(make_arrays(masks, low_shape), low_shape, flips)

    def scale_for(size_ref, height):
        """Metros por unidad del modelo: la altura de la malla si la hay; si no, el tamaño elegido."""
        if metric and metric["height_m"]:
            return metric["height_m"] / height
        return params.size / size_ref

    if is_ellipsoid(primitive):
        return _ellipsoid(masks, images, dims, scale_for, warnings, iou, marks, metric, progress, t0)

    if primitive:
        ext = np.array([w, 1.0, d])
        size_ref = float(ext.max())
        grids = PRIMITIVE_GRID_ROUND if is_round(primitive) else PRIMITIVE_GRID_SHARP
        levels = []
        for li, (n_around, n_lat) in enumerate(grids):
            _report(progress, 0.2 + 0.4 * li / len(grids), f"Generando LOD{li}...")
            v, f = primitive_mesh(primitive, ext, n_around, n_lat)
            if not is_round(primitive):
                v, f = decimate(v, f, SHARP_CLEANUP[li] * size_ref, 12)
            levels.append((v, f))
    else:
        shape, cell = grid_shape(dims, RESOLUTION)
        vol, _ = compose(make_arrays(masks, shape), shape, **flips)
        _report(progress, 0.2, "Extrayendo superficie...")
        V, F = surface_nets(np.pad(vol, PAD))
        if len(F) == 0:
            raise ValueError("No se pudo generar volumen. Revisa que las vistas correspondan al mismo objeto.")
        V, F = remove_small_components(V, F)
        V = taubin_smooth((V - PAD + 0.5) * cell, F, 5)
        lo, hi = V.min(axis=0), V.max(axis=0)
        V = V - np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2])
        ext = hi - lo
        size_ref = float(ext.max())

        levels, cur_v, cur_f = [], V, F
        for li, tol in enumerate(LOD_TOLERANCE):
            a, b = 0.3 + 0.3 * li / 4, 0.3 + 0.3 * (li + 1) / 4
            msg = f"Optimizando LOD{li}..."
            _report(progress, a, msg)
            cur_v, cur_f = decimate(cur_v, cur_f, tol * size_ref, 12,
                                    lambda f, a=a, b=b, msg=msg: _report(progress, a + (b - a) * f, msg))
            levels.append((cur_v, cur_f))

    _report(progress, 0.68, "Preparando textura...")
    box_lo = np.array([-ext[0] / 2, 0.0, -ext[2] / 2])
    atlas = Atlas(images, masks, (box_lo, box_lo + ext))
    crease = 60.0 if primitive and is_round(primitive) else 40.0
    scale = scale_for(size_ref, ext[1])

    _report(progress, 0.78, "Construyendo el modelo...")
    lods = []
    for v, f in levels:
        kind = np.zeros(len(f), int)
        verts, faces, nrm, uv = build_attributes(v, f, crease_normals(v, f, crease),
                                                 atlas.corner_uvs(v, f, kind, atlas.lower_uv))
        part = Part("body", verts.astype(np.float32), faces, nrm.astype(np.float32), uv.astype(np.float32))
        lods.append(Model([part], atlas.texture).scaled(scale, scale))

    info = {
        "mode": "primitiva" if primitive else "volumen",
        "primitive": {"axis": primitive[0], "e1": primitive[1], "e2": primitive[2]} if primitive else None,
        "primitive_iou": round(float(iou), 4),
        "watertight": bool(is_watertight(levels[0][1])),
        "texture": [atlas.size[1], atlas.size[0]],
        "seconds": round(time.time() - t0, 2),
        "triangles": [m.triangles for m in lods],
        "size": [round(x, 4) for x in lods[0].size],
        "metric": metric,
    }
    _report(progress, 0.92, "Modelo generado")
    return ShapeResult(lods=lods, warnings=warnings, info=info, marks=marks)


def _ellipsoid(masks, images, dims, scale_for, warnings, iou, marks, metric, progress, t0):
    """Esfera o elipsoide: el objeto es solo una descripción paramétrica + textura (0 triángulos propios)."""
    w, _, d = dims
    ext = np.array([w, 1.0, d])
    scale = scale_for(float(ext.max()), 1.0)

    _report(progress, 0.3, "Pintando la textura...")
    texture = bake_equirect(images, masks, ext)
    _report(progress, 0.6, "Preparando la vista previa...")
    model = preview_model(ext, texture).scaled(scale, scale)
    desc = descriptor(ext * scale)

    info = {"mode": "primitiva", "primitive": {"type": desc["type"]}, "primitive_iou": round(float(iou), 4),
            "texture": list(texture.shape[:2]), "triangles": [0],
            "size": [round(float(x), 4) for x in ext * scale], "seconds": round(time.time() - t0, 2),
            "metric": metric}
    _report(progress, 0.92, "Modelo generado")
    return ShapeResult(lods=[model], warnings=warnings, info=info, descriptor=desc, texture=texture, marks=marks)
