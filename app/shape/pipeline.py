import time
from dataclasses import dataclass, field

import numpy as np

from app.shape.geometry.cut import split_openable
from app.shape.geometry.ellipsoid import bake_equirect, descriptor, is_ellipsoid, preview_model
from app.shape.geometry.field import compose, detect_orientation, grid_shape, make_arrays
from app.shape.geometry.mesh_ops import build_attributes, crease_normals, is_watertight, remove_small_components, taubin_smooth
from app.shape.geometry.opening import find_opening
from app.shape.geometry.primitive import fit_primitive, is_round, primitive_mesh
from app.shape.geometry.protrusion import build_extras, fit_core
from app.shape.geometry.qem import decimate
from app.shape.geometry.surface_nets import surface_nets
from app.shape.model import Model, Part
from app.shape.rig.skeleton import attach_skeleton, build_skeleton, depth_finder, refine_mesh
from app.shape.spec.blueprint import Blueprint
from app.shape.texture.atlas import Atlas
from app.shape.texture.interior import Interior
from app.utils.callback_util import invoke_progress

LOD_TOLERANCE = (0.02, 0.04, 0.08, 0.15)   # error medio admitido por nivel (fracción del tamaño del objeto)
PRIMITIVE_GRID_ROUND = ((12, 6), (8, 4), (6, 2), (4, 2))   # (lados, anillos) por nivel
PRIMITIVE_GRID_SHARP = ((16, 8), (12, 6), (8, 4), (8, 4))
SHARP_CLEANUP = (0.03, 0.03, 0.05, 0.05)   # une las caras planas redundantes de cajas y cilindros
RESOLUTION = 88
LOD_TOLERANCE_RIG = (0.004, 0.008, 0.016, 0.03)   # con esqueleto la malla debe conservar el detalle para doblarse bien
RESOLUTION_RIG = 128
PAD = 2


@dataclass
class ShapeResult:
    lods: list
    warnings: list = field(default_factory=list)
    info: dict = field(default_factory=dict)
    descriptor: dict = None   # objeto paramétrico (esfera/elipsoide): no se guarda ninguna malla
    texture: object = None    # textura que acompaña al descriptor
    marks: dict = field(default_factory=dict)   # marcas del JSON por vista


def generate_shape(bp: Blueprint, progress=None) -> ShapeResult:
    """Genera el objeto a partir del Blueprint (el JSON ya interpretado): tamaño, forma, apertura y esqueleto salen de él."""
    t0 = time.time()
    warnings = list(bp.warnings)
    interior = Interior(bp.interiors)
    masks = {k: v.mask for k, v in bp.views.items()}
    images = {k: v.rgba for k, v in bp.views.items()}
    mw, mh, md = bp.dims_m
    dims = (mw / mh, 1.0, md / mh)
    metric = {"height_m": mh, "width_m": mw, "depth_m": md}
    w, _, d = dims
    marks, overlays = bp.marks, bp.marks.footprints

    # Apertura (marcas del JSON)
    opening, open_warnings = find_opening(marks, (mw, mh, md), mh)
    warnings += open_warnings
    if interior.any and not opening:
        warnings.append("Se ignoran las texturas interiores: el objeto no tiene línea de corte (no se abre).")

    # Orientación de las vistas y forma: primitiva simple si explica las siluetas, si no volumen de las vistas
    invoke_progress(progress, 0.08, "Analizando la forma del objeto...")
    flips = {}
    if {"left", "right", "top", "bottom"} & set(masks):
        flips, score = detect_orientation(masks, dims)
        if score < 0.9:
            warnings.append("Las vistas no son del todo coherentes entre sí; el modelo puede perder detalle.")
    skeleton = _skeleton(marks.joints, masks, dims, flips, (mw, mh, md), warnings)
    low_shape, _ = grid_shape(dims, 40)
    primitive, iou = fit_primitive(make_arrays(masks, low_shape), low_shape, flips)

    if is_ellipsoid(primitive):
        return _ellipsoid(masks, images, dims, flips, mh, opening, iou, marks, metric, warnings, progress, t0, interior,
                          skeleton=skeleton)

    if primitive is None:                       # ¿cuerpo elíptico con salientes (tapa, cierre...)?
        core = fit_core(masks, dims, flips)
        if core is not None:
            return _ellipsoid(masks, images, dims, flips, mh, opening, core["inliers"], marks, metric, warnings, progress,
                              t0, interior, core, overlays, skeleton)

    if primitive:
        ext = np.array([w, 1.0, d])
        size_ref = float(ext.max())
        grids = PRIMITIVE_GRID_ROUND if is_round(primitive) else PRIMITIVE_GRID_SHARP
        levels = []
        for li, (n_around, n_lat) in enumerate(grids):
            invoke_progress(progress, 0.2 + 0.4 * li / len(grids), f"Generando LOD{li}...")
            v, f = primitive_mesh(primitive, ext, n_around, n_lat)
            if not is_round(primitive):
                v, f = decimate(v, f, SHARP_CLEANUP[li] * size_ref, 12)
            levels.append((v, f))
    else:
        shape, cell = grid_shape(dims, RESOLUTION if skeleton is None else RESOLUTION_RIG)
        vol, _ = compose(make_arrays(masks, shape), shape, **flips)
        invoke_progress(progress, 0.2, "Extrayendo superficie...")
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
        for li, tol in enumerate(LOD_TOLERANCE if skeleton is None else LOD_TOLERANCE_RIG):
            a, b = 0.3 + 0.3 * li / 4, 0.3 + 0.3 * (li + 1) / 4
            msg = f"Optimizando LOD{li}..."
            invoke_progress(progress, a, msg)
            cur_v, cur_f = decimate(cur_v, cur_f, tol * size_ref, 12,
                                    lambda f, a=a, b=b, msg=msg: invoke_progress(progress, a + (b - a) * f, msg))
            levels.append((cur_v, cur_f))

    if skeleton is not None:                    # más vértices junto a las articulaciones (el esqueleto está en metros)
        unit = skeleton.scaled(float(ext[1]) / mh)
        levels = [refine_mesh(v, f, unit) for v, f in levels]
    invoke_progress(progress, 0.68, "Preparando textura...")
    box_lo = np.array([-ext[0] / 2, 0.0, -ext[2] / 2])
    atlas = Atlas(images, masks, (box_lo, box_lo + ext), flips)
    if opening:
        atlas.add_interior(interior)
    crease = 60.0 if primitive and is_round(primitive) else 40.0
    scale = mh / float(ext[1])

    invoke_progress(progress, 0.78, "Construyendo el modelo...")
    lods, openable = [], False
    for li, (v, f) in enumerate(levels):
        parts, was_split, colors = _build_parts(v, f, opening, atlas, crease)
        if li == 0 and was_split:
            atlas.paint_blocks(colors["movable"], colors["fixed"], atlas.texture[atlas._blocks[2][0], atlas._blocks[2][1], :3])
        openable = openable or was_split
        model = Model(parts, atlas.texture).scaled(scale, scale)
        lods.append(attach_skeleton(model, skeleton) if skeleton is not None else model)
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
    if skeleton is not None:
        info["skeleton"] = {"joints": len(skeleton)}
    invoke_progress(progress, 0.92, "Modelo generado")
    return ShapeResult(lods=lods, warnings=warnings, info=info, marks=marks.to_dict())


def _skeleton(joint_marks, masks, dims, flips, dims_m, warnings):
    """Esqueleto 3D (en metros) a partir de las articulaciones marcadas en las mallas, o None si no hay."""
    if not any(joint_marks.values()):
        return None
    shape, _ = grid_shape(dims, 64)
    hull, _ = compose(make_arrays(masks, shape), shape, **flips)
    cell = np.array(dims_m, np.float64) / np.array(shape)
    finder = depth_finder(hull > 0.5, np.array([-dims_m[0] / 2, 0.0, -dims_m[2] / 2]), cell)
    skeleton, notes = build_skeleton(joint_marks, dims_m, finder)
    warnings += [f"Esqueleto: {n}" for n in notes]
    return skeleton


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
               core=None, fp_masks=None, skeleton=None):
    """Esfera o elipsoide: el cuerpo es solo una descripción paramétrica + textura. Si 'core' (cuerpo ajustado sin los
    salientes) viene dado, lo que sobresale se genera aparte como malla y viaja con su pieza al abrirse."""
    w, _, d = dims
    scale = height_m / 1.0
    box = np.array([w, 1.0, d])
    ext = box if core is None else 2 * core["semi"]

    invoke_progress(progress, 0.3, "Pintando la textura...")
    texture = bake_equirect(images, masks, ext, flips, frames=None if core is None else core["frames"])
    extras = None
    if core is not None:
        invoke_progress(progress, 0.45, "Generando los salientes...")
        extras = build_extras(masks, images, fp_masks, tuple(box), flips, core)
        if extras is None:
            warnings.append("No se detectaron salientes: el objeto se genera como un elipsoide.")
    invoke_progress(progress, 0.6, "Preparando la vista previa...")
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
    invoke_progress(progress, 0.92, "Modelo generado")
    model = model.scaled(scale, scale)
    if skeleton is not None:
        attach_skeleton(model, skeleton)
        info["skeleton"] = {"joints": len(skeleton)}
    return ShapeResult(lods=[model], warnings=warnings, info=info, descriptor=desc,
                       texture=texture, marks=marks.to_dict())
