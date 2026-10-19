"""Vista previa para el usuario: las vistas, la cuadrícula con las marcas y las texturas interiores (nada de esto se usa
para calcular el modelo; el modelo sale del Blueprint)."""
import numpy as np
from PIL import Image, ImageDraw

from app.shape.rig.skeleton import PALETTE
from app.shape.spec.blueprint import Blueprint
from app.shape.spec.schema import CANVAS, VIEW_NAMES, ObjectSpec
from app.utils.pool_util import parallel_dict

GRID_STEPS = (0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100)   # metros por cuadro
GRID_MIN_PX = 60        # un cuadro de la cuadrícula ocupa al menos estos píxeles
COLORS = {"corte": (230, 30, 30), "mueve": (30, 190, 60), "bisagra": (30, 70, 220), "boton": (255, 200, 0),
          "saliente": (160, 60, 210), "malla": (110, 110, 110)}


def _origin_px(spec: ObjectSpec, key):
    """(x, y) en el lienzo del borde inferior izquierdo del cuadro del objeto en esa vista."""
    ox, oy = spec.origin(VIEW_NAMES[key])
    return ox * spec.ppm, CANVAS - oy * spec.ppm


def canvas_view(spec: ObjectSpec, bp: Blueprint, key):
    """Vista (RGBA, CANVAS × CANVAS) con el objeto centrado."""
    img = np.zeros((CANVAS, CANVAS, 4), np.uint8)
    x, y = _origin_px(spec, key)
    h, w = bp.views[key].rgba.shape[:2]
    x0, y0 = int(round(x)), int(round(y)) - h
    img[y0:y0 + h, x0:x0 + w] = bp.views[key].rgba
    return img


def canvas_grid(spec: ObjectSpec, bp: Blueprint, key):
    """Cuadrícula a escala y marcas (corte, bisagra, botón, salientes, huesos) de una vista (RGBA, CANVAS × CANVAS)."""
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox, oy = _origin_px(spec, key)
    step = next((g for g in GRID_STEPS if g * spec.ppm >= GRID_MIN_PX), GRID_STEPS[-1]) * spec.ppm
    n = int(CANVAS // step) + 1
    for i in range(-n, n + 1):          # la cuadrícula parte de la esquina inferior izquierda del objeto (origen de las medidas)
        x, y = int(round(ox + i * step)), int(round(oy - i * step))
        d.line([(x, 0), (x, CANVAS - 1)], fill=COLORS["malla"] + (255,))
        d.line([(0, y), (CANVAS - 1, y)], fill=COLORS["malla"] + (255,))
    ppm = spec.ppm
    px = lambda p: (ox + p[0] * ppm, oy - p[1] * ppm)
    m = bp.marks
    if key in m.footprints:
        mask = m.footprints[key]
        layer = np.zeros((CANVAS, CANVAS), bool)
        y0, x0 = int(round(oy)) - mask.shape[0], int(round(ox))
        layer[y0:y0 + mask.shape[0], x0:x0 + mask.shape[1]] = mask
        arr = np.asarray(img).copy()
        arr[layer] = COLORS["saliente"] + (255,)
        img = Image.fromarray(arr)
        d = ImageDraw.Draw(img)
    for a, b in m.cut.get(key, []):
        d.line([px(a), px(b)], fill=COLORS["corte"] + (255,), width=4)
    for kind, store in (("mueve", m.move), ("bisagra", m.hinge)):
        for p in store.get(key, []):
            _dot(d, px(p), 5, COLORS[kind])
    for c, r in m.button.get(key, []):
        cx, cy = px(c)
        d.ellipse([cx - r * ppm, cy - r * ppm, cx + r * ppm, cy + r * ppm], outline=COLORS["boton"] + (255,), width=4)
    for j in m.joints.get(key, []):
        c = px((j["x_m"], j["y_m"]))
        if j["parent"] is not None:
            _dot(d, c, 11, tuple(int(v) for v in PALETTE[j["parent"]]))
        _dot(d, c, 6, tuple(int(v) for v in PALETTE[j["id"]]))
    return np.asarray(img)


def _dot(draw, c, r, color):
    draw.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=color + (255,))


def build_preview(spec: ObjectSpec, bp: Blueprint) -> dict:
    """{'name', 'size', 'views': {clave: RGBA}, 'grids': {clave: RGBA}, 'interiors': {clave: RGBA}, 'notes', 'bones'}."""
    keys = list(bp.views)
    done = parallel_dict({("v", k): (lambda k=k: canvas_view(spec, bp, k)) for k in keys}
                         | {("g", k): (lambda k=k: canvas_grid(spec, bp, k)) for k in keys})
    return {"name": bp.name, "size": bp.dims_m, "views": {k: done[("v", k)] for k in keys},
            "grids": {k: done[("g", k)] for k in keys}, "interiors": dict(bp.interiors), "notes": list(bp.warnings),
            "bones": len(spec.marks.get("huesos", []))}
