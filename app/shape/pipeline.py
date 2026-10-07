import time
from dataclasses import dataclass, field

import numpy as np

from app.shape.field import compose, compute_dims, detect_orientation, grid_shape, make_arrays
from app.shape.mesh_ops import (
    is_watertight, remove_small_components, signed_volume, taubin_smooth, vertex_normals,
)
from app.shape.preprocess import load_silhouette
from app.shape.qem import decimate
from app.shape.surface_nets import surface_nets

VIEW_NAMES = {"front": "frente", "back": "detrás", "left": "izquierda", "right": "derecha", "top": "arriba"}
LOD_RATIOS = (1.0, 0.4, 0.15, 0.05)
PAD = 2


@dataclass
class ShapeParams:
    resolution: int = 96
    triangles: int = 3000
    smooth_iters: int = 6
    height: float = 1.0
    make_lods: bool = True
    auto_orient: bool = True
    flip_z: bool = False


@dataclass
class MeshData:
    vertices: np.ndarray
    faces: np.ndarray
    normals: np.ndarray

    @property
    def triangles(self) -> int:
        return len(self.faces)

    @property
    def size(self):
        return tuple((self.vertices.max(axis=0) - self.vertices.min(axis=0)).tolist())


@dataclass
class ShapeResult:
    lods: list
    warnings: list = field(default_factory=list)
    info: dict = field(default_factory=dict)


def _report(cb, frac, msg):
    if cb:
        cb(frac, msg)


def generate_shape(view_paths: dict, params: ShapeParams, progress=None) -> ShapeResult:
    t0 = time.time()
    warnings = []

    # 1. Siluetas
    masks = {}
    given = {k: p for k, p in view_paths.items() if p}
    for i, (key, path) in enumerate(given.items()):
        _report(progress, 0.08 * i / len(given), f"Leyendo vista {VIEW_NAMES[key]}...")
        masks[key], warn = load_silhouette(path)
        if warn:
            warnings.append(f"Vista {VIEW_NAMES[key]}: {warn}.")
    if "front" not in masks or not ({"left", "right"} & set(masks)):
        raise ValueError("Se necesitan al menos la vista frontal y una vista lateral.")

    # 2. Proporciones y rejilla
    w, h, d = compute_dims(masks)
    dims = (w, h, d)
    if "top" in masks:
        expected = w / d
        actual = masks["top"].shape[1] / masks["top"].shape[0]
        if abs(actual / expected - 1) > 0.18:
            warnings.append("La vista superior no concuerda con las proporciones de las demás vistas.")
    shape, cell = grid_shape(dims, params.resolution)

    # 3. Orientación y casco visual
    _report(progress, 0.10, "Detectando orientación de las vistas...")
    flips = {}
    if params.auto_orient and {"left", "right", "top"} & set(masks):
        flips, score = detect_orientation(masks, dims)
        if score < 0.9:
            warnings.append("Las vistas no son del todo coherentes entre sí; el modelo puede perder detalle.")
    _report(progress, 0.16, "Calculando volumen a partir de las vistas...")
    vol, _ = compose(make_arrays(masks, shape), shape, **flips)
    if params.flip_z:
        vol = vol[:, :, ::-1]
    vol = np.pad(vol, PAD)

    # 4. Superficie
    _report(progress, 0.26, "Extrayendo superficie...")
    V, F = surface_nets(vol)
    if len(F) == 0:
        raise ValueError("No se pudo generar volumen. Revisa que las vistas correspondan al mismo objeto.")
    V, F = remove_small_components(V, F)
    V = (V - PAD + 0.5) * cell

    _report(progress, 0.34, "Suavizando malla...")
    V = taubin_smooth(V, F, params.smooth_iters)
    dense_faces = len(F)

    # Colocación: pivote en el centro de la base, altura exacta.
    lo, hi = V.min(axis=0), V.max(axis=0)
    origin = np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2])
    scale = params.height / max(hi[1] - lo[1], 1e-9)

    # 5. Simplificación y LODs
    targets = [max(32, int(params.triangles * r)) for r in (LOD_RATIOS if params.make_lods else LOD_RATIOS[:1])]
    levels = []
    cur_v, cur_f = V, F
    for li, target in enumerate(targets):
        lo_p, hi_p = 0.38 + 0.52 * li / len(targets), 0.38 + 0.52 * (li + 1) / len(targets)
        _report(progress, lo_p, f"Optimizando LOD{li} ({target} triángulos)...")
        cur_v, cur_f = decimate(
            cur_v, cur_f, target,
            lambda f, lo_p=lo_p, hi_p=hi_p, li=li, target=target: _report(
                progress, lo_p + (hi_p - lo_p) * f, f"Optimizando LOD{li} ({target} triángulos)..."))
        levels.append((cur_v, cur_f))

    lods = []
    for v, f in levels:
        v = (v - origin) * scale
        lods.append(MeshData(v.astype(np.float32), f.astype(np.int32), vertex_normals(v, f).astype(np.float32)))

    dense_v = (V - origin) * scale
    info = {
        "seconds": round(time.time() - t0, 2),
        "grid": list(vol.shape),
        "flips": {k: bool(v) for k, v in flips.items()},
        "dense_triangles": dense_faces,
        "watertight": bool(is_watertight(lods[0].faces)),
        "volume": round(abs(signed_volume(dense_v, F)), 4),
        "size": [round(x, 4) for x in lods[0].size],
    }
    _report(progress, 0.92, "Modelo generado")
    return ShapeResult(lods=lods, warnings=warnings, info=info)
