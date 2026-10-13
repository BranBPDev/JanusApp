import itertools

import numpy as np

from app.shape.field import compose

EXPONENTS = (0.12, 0.25, 0.45, 0.7, 1.0, 1.5)   # 1 = redondo, valores bajos = aristas vivas
ACCEPT_IOU = 0.96
ACCEPT_ELLIPSOID_IOU = 0.93   # esfera/elipsoide con salientes pequeños (tapas, pestillos): la forma base sigue siendo la esfera


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
    round_ok = best is not None and best[1] == 1.0 and best[2] == 1.0 and best_iou >= ACCEPT_ELLIPSOID_IOU
    return (best if best_iou >= ACCEPT_IOU or round_ok else None), best_iou


def is_round(params) -> bool:
    return params[1] >= 0.7 and params[2] >= 0.7


def _spow(x, e):
    return np.sign(x) * np.abs(x) ** e


def primitive_mesh(params, ext, n_around: int, n_lat: int):
    """Malla regular del supercuádrico (ejes centrados en x/z, apoyada en y=0). Pocos triángulos, simétrica y cerrada."""
    axis, e1, e2 = params
    a, b = [i for i in range(3) if i != axis]
    half = np.asarray(ext, np.float64) / 2
    lon = np.arange(n_around) * 2 * np.pi / n_around
    ca, sa = _spow(np.cos(lon), e2), _spow(np.sin(lon), e2)

    verts = []
    pole = np.zeros(3)
    pole[axis] = -half[axis]
    verts.append(pole)
    for w in np.linspace(-np.pi / 2, np.pi / 2, n_lat + 1)[1:-1]:
        ring = np.zeros((n_around, 3))
        ring[:, axis] = _spow(np.sin(w), e1) * half[axis]
        radius = np.abs(np.cos(w)) ** e1
        ring[:, a] = radius * ca * half[a]
        ring[:, b] = radius * sa * half[b]
        verts.extend(ring)
    pole = np.zeros(3)
    pole[axis] = half[axis]
    verts.append(pole)
    V = np.array(verts)

    n, rings = n_around, n_lat - 1
    faces = []
    first = lambda i: 1 + i * n
    for j in range(n):
        k = (j + 1) % n
        faces.append((0, first(0) + k, first(0) + j))
        for i in range(rings - 1):
            p0, p1, p2, p3 = first(i) + j, first(i) + k, first(i + 1) + k, first(i + 1) + j
            faces += [(p0, p1, p2), (p0, p2, p3)]
        faces.append((len(V) - 1, first(rings - 1) + j, first(rings - 1) + k))
    F = np.array(faces, np.int32)

    tri = V[F]
    outward = (np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]) * tri.mean(axis=1)).sum()
    if outward < 0:
        F = F[:, ::-1]
    V[:, 1] += half[1]
    return V, np.ascontiguousarray(F)
