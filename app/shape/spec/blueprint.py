"""Del JSON a los datos que usa el cálculo del modelo: siluetas, colores, marcas y texturas interiores, todo en memoria."""
from dataclasses import dataclass, field

import numpy as np

from app.shape.geometry.relief import build_reliefs
from app.shape.spec.marks import Marks
from app.shape.spec.raster import SS, Frame, downsample, draw_layers, draw_reliefs, edge, shape_mask
from app.shape.spec.schema import INTERIOR_KEYS, VIEW_KEYS, ObjectSpec, parse_color, parse_point
from app.utils.pool_util import parallel_dict

MARGIN = 6          # píxeles de margen alrededor del cuadro de cada vista (para detectar siluetas que se salen)
INTERIOR_PX = 512
FILL_TOLERANCE = 0.03


@dataclass
class View:
    mask: np.ndarray    # silueta booleana, recortada al cuadro del objeto
    rgba: np.ndarray    # imagen RGBA uint8 con el mismo tamaño


@dataclass
class Blueprint:
    name: str
    dims_m: tuple                                # (ancho, alto, fondo) exactos del JSON
    views: dict                                  # {front, back...: View}
    marks: Marks
    interiors: dict                              # {'movable'|'fixed': RGBA uint8}
    warnings: list = field(default_factory=list)
    reliefs: list = field(default_factory=list)  # mallas de los relieves (geometry.relief.ReliefMesh)


def _view(spec: ObjectSpec, name, reliefs=()):
    """(View recortada al cuadro, avisos) de una vista descrita en el JSON."""
    w, h = spec.size(name)
    frame = Frame.around(w, h, MARGIN, spec.ppm)
    rgb, sil = draw_layers(spec.textures, spec.light, spec.views[name]["capas"], frame)
    outline = parse_color(spec.outline.get("color", "#1c1c22"), "contorno") if spec.outline else None
    rel = draw_reliefs(reliefs, VIEW_KEYS[name], (spec.width, spec.height, spec.depth), frame)
    if rel is not None:
        mask_r, rgb_r = rel
        rgb[mask_r] = rgb_r[mask_r]
        sil = sil | mask_r
        if outline:
            rgb[edge(mask_r, spec.outline.get("grosor_m", 0.0015) * frame.k / 2) & mask_r] = outline
    if spec.outline:
        rgb[edge(sil, spec.outline.get("grosor_m", 0.0015) * frame.k / 2) & sil] = parse_color(spec.outline.get("color", "#1c1c22"), "contorno")
    rgba = downsample(rgb, sil)
    box = (slice(MARGIN, rgba.shape[0] - MARGIN), slice(MARGIN, rgba.shape[1] - MARGIN))
    mask = rgba[..., 3] >= 128
    notes = []
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError(f"La vista «{name}» no dibuja nada.")
    inner = slice(MARGIN - 1, -(MARGIN - 1))             # un píxel de tolerancia (el cuadro se redondea al píxel)
    if mask.sum() > mask[inner, inner].sum():
        notes.append(f"La silueta de la vista «{name}» se sale del cuadro de «medidas_m» ({w:.3f} × {h:.3f} m).")
    bh, bw = mask[box].shape
    got = ((xs.max() - xs.min() + 1) / spec.ppm, (ys.max() - ys.min() + 1) / spec.ppm)
    if abs(got[0] - w) / w > FILL_TOLERANCE or abs(got[1] - h) / h > FILL_TOLERANCE:
        notes.append(f"La silueta de la vista «{name}» mide {got[0]:.3f} × {got[1]:.3f} m y las medidas dicen {w:.3f} × {h:.3f} m.")
    return View(mask[box], rgba[box]), notes


def _interior(spec: ObjectSpec, key):
    block = spec.interior[key]
    side = float(block.get("lado_m", max(spec.width, spec.depth)))
    frame = Frame.square(side, INTERIOR_PX)
    rgb, sil = draw_layers(spec.textures, spec.light, block["capas"], frame)
    alpha = np.ones(sil.shape, bool)
    if block.get("circular", True):
        yy, xx = np.mgrid[0:frame.h, 0:frame.w]
        r = frame.h / 2
        alpha = (xx - r + 0.5) ** 2 + (yy - r + 0.5) ** 2 <= r * r
    return downsample(rgb, alpha)


def _footprint(spec: ObjectSpec, name, items):
    """Máscara (del tamaño de la vista) de las formas de saliente marcadas en esa vista."""
    w, h = spec.size(name)
    frame = Frame.around(w, h, MARGIN, spec.ppm)
    mask = np.zeros((frame.h, frame.w), bool)
    for item in items:
        mask |= shape_mask(item, frame)
    small = mask.reshape(frame.h // SS, SS, frame.w // SS, SS).mean(axis=(1, 3)) >= 0.5
    return small[MARGIN:-MARGIN, MARGIN:-MARGIN]


def read_marks(spec: ObjectSpec) -> Marks:
    """Interpreta las marcas del JSON (sin dibujar nada), salvo las huellas de salientes que son máscaras."""
    m, out = spec.marks, Marks()
    for item in m.get("corte", []):
        out.cut.setdefault(VIEW_KEYS[item["vista"]], []).append(tuple(parse_point(p, "corte") for p in item["linea"][:2]))
    for kind, store in (("mueve", out.move), ("bisagra", out.hinge)):
        for item in m.get(kind, []):
            store.setdefault(VIEW_KEYS[item["vista"]], []).append(parse_point(item["punto"], kind))
    for item in m.get("boton", []):
        out.button.setdefault(VIEW_KEYS[item["vista"]], []).append((parse_point(item["centro"], "boton"), float(item.get("radio", 0.01))))
    for b in m.get("huesos", []):
        for view, key in VIEW_KEYS.items():
            if view in b:
                x, y = parse_point(b[view], "huesos")
                out.joints.setdefault(key, []).append({"id": b["id"], "parent": b.get("padre"), "x_m": x, "y_m": y})
    return out


def build_blueprint(spec: ObjectSpec) -> Blueprint:
    """Calcula (en paralelo) las siluetas con su color, las huellas de salientes y las texturas interiores del JSON."""
    reliefs = build_reliefs(spec.reliefs, spec.textures, (spec.width, spec.height, spec.depth)) if spec.reliefs else []
    tasks = {("view", v): (lambda v=v: _view(spec, v, reliefs)) for v in spec.views}
    by_view = {}
    for item in spec.marks.get("salientes", []):
        by_view.setdefault(item["vista"], []).append(item)
    tasks |= {("foot", v): (lambda v=v, items=items: _footprint(spec, v, items)) for v, items in by_view.items()}
    tasks |= {("int", k): (lambda k=k: _interior(spec, k)) for k in spec.interior}
    done = parallel_dict(tasks)

    marks, warnings = read_marks(spec), []
    views = {}
    for (kind, name), value in done.items():
        if kind == "view":
            views[VIEW_KEYS[name]] = value[0]
            warnings += value[1]
        elif kind == "foot":
            marks.footprints[VIEW_KEYS[name]] = value
    interiors = {INTERIOR_KEYS[k]: done[("int", k)] for k in spec.interior}
    return Blueprint(spec.name, (spec.width, spec.height, spec.depth), views, marks, interiors, warnings, reliefs)
