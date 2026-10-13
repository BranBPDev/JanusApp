import time
from dataclasses import dataclass, field

import numpy as np

from app.shape.atlas import Atlas
from app.shape.cut import split_openable
from app.shape.ellipsoid import bake_equirect, descriptor, is_ellipsoid, preview_model
from app.shape.interior import Interior
from app.shape.field import compose, compute_dims, detect_orientation, grid_shape, make_arrays
from app.shape.naming import VIEW_NAMES
from app.shape.mesh_ops import build_attributes, crease_normals, is_watertight, remove_small_components, taubin_smooth
from app.shape.metric import CELL_M, analyze_overlay, metric_dims
from app.shape.model import Model, Part
from app.shape.opening import find_opening
from app.shape.preprocess import load_silhouette
from app.shape.primitive import fit_primitive, is_round, primitive_mesh
from app.shape.protrusion import build_extras, fit_core, footprints
from app.shape.qem import decimate
from app.shape.surface_nets import surface_nets

LOD_TOLERANCE = (0.02, 0.04, 0.08, 0.15)   # error medio admitido por nivel (fracción del tamaño del objeto)
PRIMITIVE_GRID_ROUND = ((12, 6), (8, 4), (6, 2), (4, 2))   # (lados, anillos) por nivel
PRIMITIVE_GRID_SHARP = ((16, 8), (12, 6), (8, 4), (8, 4))
SHARP_CLEANUP = (0.03, 0.03, 0.05, 0.05)   # une las caras planas redundantes de cajas y cilindros
RESOLUTION = 88
PAD = 2


@dataclass
class ShapeResult:
    lods: list
    warnings: list = field(default_factory=list)
    info: dict = field(default_factory=dict)
    descriptor: dict = None   # objeto paramétrico (esfera/elipsoide): no se guarda ninguna malla
    texture: object = None    # textura que acompaña al descriptor
    marks: dict = field(default_factory=dict)   # marcas de las mallas por vista


def _report(cb, frac, msg):
    if cb:
        cb(frac, msg)


def generate_shape(view_paths: dict, grid_paths: dict, progress=None, interior_paths: dict = None) -> ShapeResult:
    """Genera el objeto a partir de las vistas y sus mallas. Todo (tamaño, forma, apertura) sale de ellas.
    'interior_paths' ({'movable': ruta, 'fixed': ruta}) son las texturas interiores opcionales de la tapa y la base."""
    t0 = time.time()
    warnings = []
    interior = Interior.load(interior_paths)

    given = {k: p for k, p in view_paths.items() if p}
    if "front" not in given or not ({"left", "right"} & set(given)):
        raise ValueError("Se necesitan al menos la vista frontal y una vista lateral.")
    missing = [VIEW_NAMES[k] for k in given if not (grid_paths or {}).get(k)]
    if missing:
        raise ValueError("Falta la malla de: " + ", ".join(missing) + ".")

    views = {}
    for i, (key, path) in enumerate(given.items()):
        _report(progress, 0.06 * i / len(given), f"Leyendo vista {VIEW_NAMES[key]}...")
        views[key] = load_silhouette(path)
        if views[key].warning:
            warnings.append(f"Vista {VIEW_NAMES[key]}: {views[key].warning}.")
    masks = {k: v.mask for k, v in views.items()}
    images = {k: v.rgba for k, v in views.items()}

    # Mallas: escala exacta y marcas
    cells, marks, overlays = {}, {}, {}
    for key, path in grid_paths.items():
        if key not in views:
            continue
        v = views[key]
        x0, y0, x1, y1 = v.box
        found = analyze_overlay(path, v.original_size, (x0 * v.scale, y0 * v.scale, x1 * v.scale, y1 * v.scale), CELL_M)
        if found is None:
            raise ValueError(f"No se detecta una cuadrícula regular en la malla {VIEW_NAMES[key]}.")
        if found["warning"]:
            warnings.append(f"Malla {VIEW_NAMES[key]}: {found['warning'].strip()}.")
        cells[key] = found["cell_px"]
        marks[key] = found["marks"]
        overlays[key] = found["footprint"]

    (mw, mh, md), metric_warnings = metric_dims(views, cells, CELL_M)
    warnings += metric_warnings
    dims = (mw / mh, 1.0, md / mh)
    metric = {"cell_m": CELL_M, "height_m": mh, "width_m": mw, "depth_m": md}
    w, _, d = dims
    for key in ("top", "bottom"):
        if key in masks and abs(masks[key].shape[1] / masks[key].shape[0] / (w / d) - 1) > 0.18:
            warnings.append(f"La vista {VIEW_NAMES[key]} no concuerda con las proporciones de las demás vistas.")

    # Apertura (marcas de las mallas)
    opening, open_warnings = find_opening(marks, (mw, mh, md), mh)
    warnings += open_warnings
    if interior.any and not opening:
        warnings.append("Se ignoran las texturas interiores: el objeto no tiene línea de corte (no se abre).")

    # Orientación de las vistas y forma: primitiva simple si explica las siluetas, si no volumen de las vistas
    _report(progress, 0.08, "Analizando la forma del objeto...")
    flips = {}
    if {"left", "right", "top", "bottom"} & set(masks):
        flips, score = detect_orientation(masks, dims)
        if score < 0.9:
            warnings.append("Las vistas no son del todo coherentes entre sí; el modelo puede perder detalle.")
    low_shape, _ = grid_shape(dims, 40)
    primitive, iou = fit_primitive(make_arrays(masks, low_shape), low_shape, flips)

    if is_ellipsoid(primitive):
        return _ellipsoid(masks, images, dims, flips, mh, opening, iou, marks, metric, warnings, progress, t0, interior)

    if primitive is None:                       # ¿cuerpo elíptico con salientes (tapa, cierre...)?
        core = fit_core(masks, dims, flips)
        if core is not None:
            return _ellipsoid(masks, images, dims, flips, mh, opening, core["inliers"], marks, metric, warnings, progress,
                              t0, interior, core, footprints(overlays, views))

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
    atlas = Atlas(images, masks, (box_lo, box_lo + ext), flips)
    if opening:
        atlas.add_interior(interior)
    crease = 60.0 if primitive and is_round(primitive) else 40.0
    scale = mh / float(ext[1])

    _report(progress, 0.78, "Construyendo el modelo...")
    lods, openable = [], False
    for li, (v, f) in enumerate(levels):
        parts, was_split, colors = _build_parts(v, f, opening, atlas, crease)
        if li == 0 and was_split:
            atlas.paint_blocks(colors["movable"], colors["fixed"], atlas.texture[atlas._blocks[2][0], atlas._blocks[2][1], :3])
        openable = openable or was_split
        lods.append(Model(parts, atlas.texture).scaled(scale, scale))
    if opening and not openable:
        warnings.append("No se pudo abrir el objeto por la línea de corte marcada (el corte no da una sola sección).")
    if interior.any and opening and not openable:
        warnings.append("Se ignoran las texturas interiores: el objeto no se pudo abrir.")

    info = {
        "mode": "primitiva" if primitive else "volumen",
        "primitive": {"axis": primitive[0], "e1": primitive[1], "e2": primitive[2]} if primitive else None,
        "primitive_iou": round(float(iou), 4),
        "openable": openable,
        "watertight": bool(is_watertight(levels[0][1])),
        "texture": [atlas.size[1], atlas.size[0]],
        "seconds": round(time.time() - t0, 2),
        "triangles": [m.triangles for m in lods],
        "size": [round(x, 4) for x in lods[0].size],
        "metric": metric,
    }
    _report(progress, 0.92, "Modelo generado")
    return ShapeResult(lods=lods, warnings=warnings, info=info, marks=marks)


def _build_parts(V, F, opening, atlas, crease):
    """Una pieza ('body') o, si hay marca de corte, pieza fija + pieza móvil huecas con bisagra."""
    split = split_openable(V, F, opening) if opening else None
    if split is None:
        specs = [("body", V, F, np.zeros(len(F), int), atlas.fixed_uv, {})]
    else:
        fixed, moving, hinge, axis, angle = split
        specs = [("fixed", *fixed, atlas.fixed_uv, {}),
                 ("movable", *moving, atlas.moving_uv, {"origin": hinge, "axis": axis, "open_angle": angle})]

    parts, colors = [], {}
    tex = atlas.texture
    for name, v, f, kind, interior_uv, extra in specs:
        uvs = atlas.corner_uvs(v, f, kind, interior_uv)
        if atlas.interior is not None and split is not None and name in ("movable", "fixed"):
            uvs = atlas.interior.remap(uvs, kind, v, f, name, opening["normal"], opening["point"],
                                       (atlas.ext[0], atlas.ext[2]))
        c = uvs[kind == 0].mean(axis=1)
        th, tw = tex.shape[:2]
        colors[name] = tex[np.clip((c[:, 1] * th).astype(int), 0, th - 1), np.clip((c[:, 0] * tw).astype(int), 0, tw - 1), :3].mean(axis=0)
        verts, faces, nrm, uv = build_attributes(v, f, crease_normals(v, f, crease), uvs)
        parts.append(Part(name, verts.astype(np.float32), faces, nrm.astype(np.float32), uv.astype(np.float32), **extra))
    return parts, split is not None, colors


def _ellipsoid(masks, images, dims, flips, height_m, opening, iou, marks, metric, warnings, progress, t0, interior=None,
               core=None, fp_masks=None):
    """Esfera o elipsoide: el cuerpo es solo una descripción paramétrica + textura. Si 'core' (cuerpo ajustado sin los
    salientes) viene dado, lo que sobresale se genera aparte como malla y viaja con su pieza al abrirse."""
    w, _, d = dims
    scale = height_m / 1.0
    box = np.array([w, 1.0, d])
    ext = box if core is None else 2 * core["semi"]

    _report(progress, 0.3, "Pintando la textura...")
    texture = bake_equirect(images, masks, ext, flips, frames=None if core is None else core["frames"])
    extras = None
    if core is not None:
        _report(progress, 0.45, "Generando los salientes...")
        extras = build_extras(masks, images, fp_masks, tuple(box), flips, core)
        if extras is None:
            warnings.append("No se detectaron salientes: el objeto se genera como un elipsoide.")
    _report(progress, 0.6, "Preparando la vista previa...")
    model, open_info = preview_model(ext, texture, opening, interior, None if core is None else core["center"], extras)
    if opening and open_info is None:
        warnings.append("No se pudo abrir el objeto por la línea de corte marcada (el corte no da una sola sección).")
        if interior and interior.any:
            warnings.append("Se ignoran las texturas interiores: el objeto no se pudo abrir.")
    extra_tris = 0 if extras is None else len(extras["F"])
    desc = descriptor(ext * scale, open_info, opening, scale, model.triangles,
                      None if core is None else core["center"] * scale, extra_tris)

    info = {"mode": "primitiva", "primitive": {"type": desc["type"]}, "primitive_iou": round(float(iou), 4),
            "openable": open_info is not None, "texture": list(model.texture.shape[:2]), "triangles": [model.triangles],
            "size": [round(float(x), 4) for x in box * scale], "seconds": round(time.time() - t0, 2),
            "metric": metric}
    if extras is not None:
        info["extras"] = {"triangles": extra_tris}
    _report(progress, 0.92, "Modelo generado")
    return ShapeResult(lods=[model.scaled(scale, scale)], warnings=warnings, info=info, descriptor=desc,
                       texture=texture, marks=marks)
