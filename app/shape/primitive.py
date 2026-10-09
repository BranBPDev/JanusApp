import itertools

import numpy as np

from app.shape.field import compose

EXPONENTS = (0.12, 0.25, 0.45, 0.7, 1.0, 1.5)   # 1 = redondo, valores bajos = aristas vivas
ACCEPT_IOU = 0.96


def _implicit(shape, axis, e1, e2, extra=0):
    """F(x,y,z) del supercuádrico (F<=1 dentro) sobre la rejilla normalizada [-1,1]^3 (con 'extra' celdas de margen)."""
    coords = [((np.arange(-extra, n + extra) + 0.5) / n * 2 - 1) for n in shape]
    grid = np.meshgrid(*coords, indexing="ij")
    main = np.abs(grid[axis])
    a, b = [np.abs(g) for i, g in enumerate(grid) if i != axis]
    section = a ** (2 / e2) + b ** (2 / e2)
    return section ** (e2 / e1) + main ** (2 / e1)


def _iou(vol_in, targets):
    total = 0.0
    for t, ax in targets:
        proj, truth = vol_in.any(axis=ax), t > 0.5
        union = (proj | truth).sum()
        total += (proj & truth).sum() / max(1, union)
    return total / len(targets)


def fit_primitive(arrays, shape, flips):
    """Ajusta el supercuádrico (esfera, elipsoide, cilindro, caja, cápsula...) que mejor explica las siluetas.
    Devuelve (params, iou) o (None, iou) si ninguna primitiva simple las explica."""
    _, targets = compose(arrays, shape, **flips)
    best, best_iou = None, 0.0
    for axis, e1, e2 in itertools.product(range(3), EXPONENTS, EXPONENTS):
        iou = _iou(_implicit(shape, axis, e1, e2) <= 1.0, targets)
        if iou > best_iou + 1e-9:
            best, best_iou = (axis, e1, e2), iou
    return (best if best_iou >= ACCEPT_IOU else None), best_iou


def primitive_field(params, shape, pad):
    """Campo escalar (iso 0.5 en la superficie) del supercuádrico, ya con margen para la extracción de superficie."""
    axis, e1, e2 = params
    f = _implicit(shape, axis, e1, e2, extra=pad)
    return (0.5 - 0.35 * np.log(np.maximum(f, 1e-6))).astype(np.float32)
