from collections import deque

import numpy as np
from PIL import Image

LINE_FRACTION = 0.5     # una línea de la malla ocupa al menos la mitad del lado de la imagen
COLOR_TOLERANCE = 60


def _ink(img: np.ndarray) -> np.ndarray:
    """Píxeles dibujados de la capa (la malla puede venir con transparencia o sobre un fondo liso)."""
    if (img[..., 3] < 250).mean() > 0.2:
        return img[..., 3] > 40
    rgb = img[..., :3].astype(np.int32)
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    return np.abs(rgb - np.median(border, axis=0)).sum(axis=2) > COLOR_TOLERANCE


def _candidates(ink, arr, axis):
    """Líneas completas (columnas si axis=0, filas si axis=1): (centro, color medio)."""
    profile = ink.sum(axis=axis) / ink.shape[axis]
    idx = np.flatnonzero(profile >= LINE_FRACTION)
    if len(idx) == 0:
        return []
    out = []
    for g in np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1):
        line = arr[:, g] if axis == 0 else arr[g]
        sel = ink[:, g] if axis == 0 else ink[g]
        out.append((float(g.mean()), line[sel][:, :3].mean(axis=0)))
    return out


def _grid_lines(cols, rows):
    """Se queda con las líneas del color dominante (la cuadrícula); las marcas largas de otro color se descartan."""
    colors = [c for _, c in cols + rows]
    if not colors:
        return [], []
    keys = [tuple((np.asarray(c) // 48).astype(int)) for c in colors]
    best = max(set(keys), key=keys.count)
    keep = lambda lines: [c for (c, col) in lines if tuple((np.asarray(col) // 48).astype(int)) == best]
    return keep(cols), keep(rows)


def _spacing(centers):
    """Distancia entre líneas de la cuadrícula (tolera alguna línea ausente) o None si no es regular."""
    if len(centers) < 3:
        return None
    d = np.diff(centers)
    med = float(np.median(d))
    if med < 4:
        return None
    k = np.maximum(np.round(d / med), 1)
    if (np.abs(d - k * med) / med).max() > 0.08:
        return None
    return float(d.sum() / k.sum())


def _name(rgb):
    return "#{:02x}{:02x}{:02x}".format(*[int(round(c)) for c in rgb])


def _components(points):
    """Componentes conexas (8 vecinos) de un conjunto de píxeles (y, x)."""
    left, comps = set(points), []
    while left:
        seed = left.pop()
        comp, queue = [seed], deque([seed])
        while queue:
            y, x = queue.popleft()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    n = (y + dy, x + dx)
                    if n in left:
                        left.remove(n)
                        comp.append(n)
                        queue.append(n)
        comps.append(comp)
    return comps


def analyze_overlay(path, original_size, box_px, cell_m):
    """Lee la capa de malla de una vista. Devuelve {'cell_px', 'marks', 'warning'} o None si no hay cuadrícula legible.
    'box_px' = (x0, y0, x1, y1) del objeto en píxeles de la imagen original (origen de las medidas de las marcas)."""
    img = Image.open(path).convert("RGBA")
    warning = None
    if img.size != tuple(original_size):
        img = img.resize(tuple(original_size), Image.NEAREST)
        warning = "la malla no tiene el tamaño de la imagen: se ha reescalado"
    arr = np.asarray(img)
    ink = _ink(arr)
    h, w = ink.shape

    cols, rows = _grid_lines(_candidates(ink, arr, 0), _candidates(ink, arr, 1))
    sx, sy = _spacing(cols), _spacing(rows)
    if sx is None or sy is None:
        return None
    if abs(sx - sy) / max(sx, sy) > 0.05:
        warning = (warning or "") + " los cuadros no son cuadrados"
    cell_px = (sx + sy) / 2

    # Color de la cuadrícula = el de los píxeles sobre sus líneas; lo demás son marcas
    on_line = np.zeros_like(ink)
    for c in cols:
        on_line[:, max(0, int(round(c)) - 1):int(round(c)) + 2] = True
    for r in rows:
        on_line[max(0, int(round(r)) - 1):int(round(r)) + 2, :] = True
    grid_color = np.median(arr[ink & on_line][:, :3].astype(np.float64), axis=0)
    dist = np.abs(arr[..., :3].astype(np.float64) - grid_color).sum(axis=2)
    marks_mask = ink & ~(on_line & (dist < COLOR_TOLERANCE))

    x0, _, _, y1 = box_px
    to_m = lambda x, y: [round((x - x0) / cell_px * cell_m, 4), round((y1 - y) / cell_px * cell_m, 4)]
    marks = []
    ys, xs = np.nonzero(marks_mask)
    if len(ys):
        bins = (arr[ys, xs, :3] // 64).astype(int)
        key = bins[:, 0] * 16 + bins[:, 1] * 4 + bins[:, 2]
        for k in np.unique(key):
            sel = key == k
            if sel.sum() < 12:
                continue
            color = arr[ys[sel], xs[sel], :3].mean(axis=0)
            comps = _components(list(zip(ys[sel].tolist(), xs[sel].tolist())))
            comps = [c for c in comps if len(c) >= 3]
            if not comps:
                continue
            sizes = [max(max(p[0] for p in c) - min(p[0] for p in c), max(p[1] for p in c) - min(p[1] for p in c)) + 1
                     for c in comps]
            if len(comps) >= 4 and float(np.median(sizes)) <= 0.12 * cell_px + 2:
                style = "puntos"
            elif len(comps) >= 4 and float(np.median(sizes)) <= 1.2 * cell_px:
                style = "discontinua"
            else:
                style = "continua"
            centers = [to_m(np.mean([p[1] for p in c]), np.mean([p[0] for p in c])) for c in comps[:200]]
            allx = [p[1] for c in comps for p in c]
            ally = [p[0] for c in comps for p in c]
            marks.append({"color": _name(color), "style": style, "components": len(comps),
                          "bbox_m": [*to_m(min(allx), max(ally)), *to_m(max(allx), min(ally))], "points_m": centers})
    return {"cell_px": cell_px, "marks": marks, "warning": warning}


def view_sizes_m(view, cell_px, cell_m):
    """Ancho y alto del objeto en metros según la malla de esa vista."""
    h, w = view.mask.shape
    k = view.scale / cell_px * cell_m
    return w * k, h * k


def metric_dims(views: dict, cells: dict, cell_m: float):
    """(ancho, alto, fondo) en metros combinando todas las vistas con malla, y avisos de incoherencia."""
    sizes = {k: view_sizes_m(views[k], c, cell_m) for k, c in cells.items()}
    W = [sizes[k][0] for k in ("front", "back") if k in sizes]
    H = [sizes[k][1] for k in ("front", "back", "left", "right") if k in sizes]
    D = [sizes[k][0] for k in ("left", "right") if k in sizes]
    if "top" in sizes:
        W.append(sizes["top"][0])
        D.append(sizes["top"][1])
    warnings = []
    out = []
    for name, vals in (("ancho", W), ("alto", H), ("fondo", D)):
        if len(vals) >= 2 and (max(vals) - min(vals)) / max(vals) > 0.06:
            warnings.append(f"Las mallas dan {name}s distintos según la vista ({min(vals):.2f} - {max(vals):.2f} m).")
        out.append(float(np.mean(vals)) if vals else None)
    return tuple(out), warnings
