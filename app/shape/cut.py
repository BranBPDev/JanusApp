from collections import defaultdict

import numpy as np

from app.shape.qem import decimate

WALL = 0.93           # el interior es el exterior reducido a este factor
OPEN_ANGLE = -75.0    # grados de apertura sobre el eje X


def _cut(V, F, y):
    d = V[:, 1] - y
    d = np.where(np.abs(d) < 1e-9, 1e-9, d)
    extra, edge_map = [], {}

    def point(a, b):
        key = (a, b) if a < b else (b, a)
        if key not in edge_map:
            t = d[a] / (d[a] - d[b])
            p = V[a] + t * (V[b] - V[a])
            p[1] = y
            edge_map[key] = len(V) + len(extra)
            extra.append(p)
        return edge_map[key]

    lower, upper, segs = [], [], []
    for tri in F.tolist():
        up = [d[v] > 0 for v in tri]
        n_up = sum(up)
        if n_up in (0, 3):
            (upper if n_up == 3 else lower).append(tri)
            continue
        i = up.index(n_up == 1)          # vértice que queda solo en su lado
        l, p, q = tri[i], tri[(i + 1) % 3], tri[(i + 2) % 3]
        i1, i2 = point(l, p), point(l, q)
        segs.append((i1, i2))
        lone_side, other_side = (upper, lower) if up[i] else (lower, upper)
        lone_side.append((l, i1, i2))
        other_side += [(i1, p, q), (i1, q, i2)]
    return np.vstack([V] + [np.array(extra)]) if extra else V, np.array(lower), np.array(upper), segs


def _single_loop(segs):
    adj = defaultdict(list)
    for a, b in segs:
        adj[a].append(b)
        adj[b].append(a)
    if not adj or any(len(n) != 2 for n in adj.values()):
        return None
    start = next(iter(adj))
    loop, prev, cur = [start], None, start
    while True:
        a, b = adj[cur]
        nxt = a if a != prev else b
        if nxt == start:
            break
        loop.append(nxt)
        prev, cur = cur, nxt
        if len(loop) > len(adj):
            return None
    return loop if len(loop) == len(adj) else None  # un único contorno


def _hollow(V, F, ring, c3, rim_sign, inner_tol):
    """Pieza hueca: exterior + carcasa interior reducida + borde que las une. Devuelve (V, F, kind)."""
    used = np.unique(F)
    remap = np.full(len(V), -1)
    remap[used] = np.arange(len(used))
    Vp, Fp = V[used], remap[F]
    ring = remap[ring]
    n = len(Vp)

    # carcasa interior: copia reducida del exterior y simplificada más (casi no se ve); el borde queda fijo
    inner_v, inner_f, remap = decimate(c3 + WALL * (Vp - c3), Fp, inner_tol, 12, locked=ring, return_map=True)
    r = len(ring)
    outer_ring, inner_ring = Vp[ring], c3 + WALL * (Vp[ring] - c3)
    base = n + len(inner_v)
    strip = []
    for i in range(r):
        j = (i + 1) % r
        strip += [(base + i, base + j, base + r + j), (base + i, base + r + j, base + r + i)]
    strip = np.array(strip)
    allv = np.vstack([Vp, inner_v, outer_ring, inner_ring])
    t = allv[strip]
    ny = np.cross(t[0, 1] - t[0, 0], t[0, 2] - t[0, 0])[1]
    if ny * rim_sign < 0:
        strip = strip[:, ::-1]
    faces = np.vstack([Fp, inner_f[:, ::-1] + n, strip])
    kind = np.concatenate([np.zeros(len(Fp), int), np.ones(len(inner_f) + len(strip), int)])
    return allv, faces.astype(np.int32), kind


def split_openable(V, F, y_s, inner_tol):
    """Corta el objeto por la junta y vacía las dos mitades. Devuelve (base, tapa, bisagra) o None si no es posible.
    Cada pieza es (V, F, kind) con kind 0 = exterior, 1 = interior/borde."""
    Va, lower, upper, segs = _cut(V, F, y_s)
    loop = _single_loop(segs)
    if loop is None or len(lower) < 8 or len(upper) < 8:
        return None
    ring = np.array(loop)
    pts = Va[ring]
    c3 = np.array([pts[:, 0].mean(), y_s, pts[:, 2].mean()])
    hinge = (float(c3[0]), float(y_s), float(pts[:, 2].min()))
    return _hollow(Va, lower, ring, c3, +1, inner_tol), _hollow(Va, upper, ring, c3, -1, inner_tol), hinge
