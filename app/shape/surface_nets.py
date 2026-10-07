import numpy as np

_CORNERS = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1))
_EDGES = ((0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7))


def surface_nets(field: np.ndarray, iso: float = 0.5):
    """Superficie del campo escalar (Naive Surface Nets, vectorizado). Devuelve (vértices en índices de rejilla, caras).
    El campo debe tener el exterior (valores < iso) en todo el borde."""
    nx, ny, nz = field.shape
    cx, cy, cz = nx - 1, ny - 1, nz - 1
    inside = field > iso

    count = np.zeros((cx, cy, cz), np.uint8)
    for dx, dy, dz in _CORNERS:
        count += inside[dx:dx + cx, dy:dy + cy, dz:dz + cz]
    mixed = (count > 0) & (count < 8)
    cells = np.argwhere(mixed)
    m = len(cells)
    if m == 0:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int32)

    vid = np.full((cx, cy, cz), -1, np.int32)
    vid[mixed] = np.arange(m, dtype=np.int32)

    # Un vértice por celda: media de los cruces de las aristas con la superficie.
    ci, cj, ck = cells.T
    acc = np.zeros((m, 3))
    num = np.zeros(m)
    for a, b in _EDGES:
        pa, pb = _CORNERS[a], _CORNERS[b]
        fa = field[ci + pa[0], cj + pa[1], ck + pa[2]]
        fb = field[ci + pb[0], cj + pb[1], ck + pb[2]]
        cross = (fa > iso) != (fb > iso)
        den = np.where(cross, fb - fa, 1.0)
        t = np.where(cross, (iso - fa) / den, 0.0)
        for ax in range(3):
            acc[:, ax] += cross * (pa[ax] + t * (pb[ax] - pa[ax]))
        num += cross
    pos = cells + acc / num[:, None]

    # Un quad por cada arista de la rejilla que cambia de signo.
    tris = []
    for axis in range(3):
        sa, sb = [slice(None)] * 3, [slice(None)] * 3
        sa[axis], sb[axis] = slice(0, -1), slice(1, None)
        pa_in, pb_in = inside[tuple(sa)], inside[tuple(sb)]
        idx = np.argwhere(pa_in != pb_in)
        if len(idx) == 0:
            continue
        i, j, k = idx.T
        if axis == 0:
            q = (vid[i, j - 1, k - 1], vid[i, j, k - 1], vid[i, j, k], vid[i, j - 1, k])
        elif axis == 1:
            q = (vid[i - 1, j, k - 1], vid[i - 1, j, k], vid[i, j, k], vid[i, j, k - 1])
        else:
            q = (vid[i - 1, j - 1, k], vid[i, j - 1, k], vid[i, j, k], vid[i - 1, j, k])
        q = np.stack(q, axis=1)
        q = np.where(pa_in[i, j, k][:, None], q, q[:, ::-1])  # normales hacia fuera
        q = q[(q >= 0).all(axis=1)]

        # diagonal más corta para triángulos más regulares
        p = pos[q]
        d02 = ((p[:, 0] - p[:, 2]) ** 2).sum(1)
        d13 = ((p[:, 1] - p[:, 3]) ** 2).sum(1)
        use02 = (d02 <= d13)[:, None]
        tris.append(np.where(use02, q[:, [0, 1, 2]], q[:, [1, 2, 3]]))
        tris.append(np.where(use02, q[:, [0, 2, 3]], q[:, [1, 3, 0]]))

    faces = np.concatenate(tris).astype(np.int32) if tris else np.zeros((0, 3), np.int32)
    return pos, faces
