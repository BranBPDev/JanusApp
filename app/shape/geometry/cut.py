from collections import defaultdict

import numpy as np

WALL = 0.93           # profundidad relativa del interior
OPEN_ANGLE = 75.0     # grados de apertura (el signo se decide solo, hacia el lado que se aleja)
AXIS = np.array([1.0, 0.0, 0.0])


def _cut(V, F, point, normal, button=None):
    d = (V - point) @ normal
    g = None
    if button:                            # disco del botón (cara frontal): entero a la tapa, con su hueco en la base
        c, r = button["center"], button["radius"]
        g = np.where(V[:, 2] > 0, r - np.hypot(V[:, 0] - c[0], V[:, 1] - c[1]), -1.0)
        d = np.maximum(d, g)
    snap = 1e-6 * max(float(np.ptp(d)), 1e-9)
    on = np.abs(d) < snap                 # los vértices sobre el plano se reutilizan, no se parten las aristas
    up_v = (d > 0) | on
    extra, edge_map = [], {}

    def cut_point(a, b):
        if on[a]:
            return a
        if on[b]:
            return b
        key = (a, b) if a < b else (b, a)
        if key not in edge_map:
            t = d[a] / (d[a] - d[b])
            p = V[a] + t * (V[b] - V[a])
            if g is None or (g[a] <= 0 and g[b] <= 0):
                p = p - ((p - point) @ normal) * normal
            edge_map[key] = len(V) + len(extra)
            extra.append(p)
        return edge_map[key]

    lower, upper, segs = [], [], []

    def add(side, tri):
        if len(set(tri)) == 3:
            side.append(tri)

    for tri in F.tolist():
        up = [bool(up_v[v]) for v in tri]
        n_up = sum(up)
        if n_up in (0, 3):
            (upper if n_up == 3 else lower).append(tuple(tri))
            continue
        i = up.index(n_up == 1)          # vértice que queda solo en su lado
        l, p, q = tri[i], tri[(i + 1) % 3], tri[(i + 2) % 3]
        i1, i2 = cut_point(l, p), cut_point(l, q)
        if i1 != i2:
            segs.append((i1, i2))
        lone_side, other_side = (upper, lower) if up[i] else (lower, upper)
        add(lone_side, (l, i1, i2))
        add(other_side, (i1, p, q))
        add(other_side, (i1, q, i2))
    Va = np.vstack([V, np.array(extra)]) if extra else V
    return Va, np.array(lower), np.array(upper), segs


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


def _hollow(V, F, ring, c3, into):
    """Pieza abierta: exterior + una cúpula interior de pocos triángulos que arranca en el borde. (V, F, kind).
    'into' = dirección (unitaria) desde el plano hacia el interior de la pieza."""
    used = np.unique(F)
    remap = np.full(len(V), -1)
    remap[used] = np.arange(len(used))
    Vp, Fp = V[used], remap[F]
    ring_pts = Vp[remap[ring]]
    r = len(ring)

    rel = Vp - c3
    dist = rel @ into
    rad = np.linalg.norm(rel - dist[:, None] * into, axis=1)
    height = max(float(dist.max()), 1e-9)
    d1 = 0.45 * WALL * height
    band = (dist > 0.6 * d1) & (dist < 1.4 * d1)
    ring_rel = ring_pts - c3
    ring_flat = ring_rel - (ring_rel @ into)[:, None] * into
    ring_r = np.linalg.norm(ring_flat, axis=1).mean()
    s1 = float(np.clip(0.85 * (rad[band].mean() if band.any() else 0.7 * rad.max()) / max(ring_r, 1e-9), 0.2, 0.9))
    ring1 = c3 + into * d1 + ring_flat * s1
    apex = c3 + into * WALL * height

    n = len(Vp)
    dome_v = np.vstack([ring_pts, ring1, apex[None]])
    base, mid, top = n, n + r, n + 2 * r
    dome = []
    for i in range(r):
        j = (i + 1) % r
        dome += [(base + i, base + j, mid + j), (base + i, mid + j, mid + i), (mid + i, mid + j, top)]
    dome = np.array(dome)
    allv = np.vstack([Vp, dome_v])
    t = allv[dome]
    normal = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    if (normal * (c3 - t.mean(axis=1))).sum() < 0:   # las caras miran hacia el hueco
        dome = dome[:, ::-1]
    faces = np.vstack([Fp, dome])
    kind = np.concatenate([np.zeros(len(Fp), int), np.ones(len(dome), int)])
    return allv, faces.astype(np.int32), kind


def _angle(moving_v, hinge, normal):
    """Signo del giro sobre el eje X que aleja la parte móvil del resto."""
    c = moving_v.mean(axis=0) - hinge
    best, best_gain = OPEN_ANGLE, -np.inf
    for theta in (OPEN_ANGLE, -OPEN_ANGLE):
        t = np.radians(theta)
        rot = np.array([[1, 0, 0], [0, np.cos(t), -np.sin(t)], [0, np.sin(t), np.cos(t)]])
        gain = ((rot @ c) - c) @ normal
        if gain > best_gain:
            best, best_gain = theta, gain
    return best


def split_openable(V, F, opening):
    """Corta por el plano de 'opening' y vacía las dos piezas. Devuelve (fija, móvil, bisagra, eje, ángulo) o None.
    Cada pieza es (V, F, kind) con kind 0 = exterior, 1 = interior."""
    point, normal = np.asarray(opening["point"], np.float64), np.asarray(opening["normal"], np.float64)
    Va, lower, upper, segs = _cut(V, F, point, normal, opening.get("button"))
    loop = _single_loop(segs)
    if loop is None or len(lower) < 4 or len(upper) < 4:
        return None
    ring = np.array(loop)
    pts = Va[ring]
    c3 = pts.mean(axis=0)
    c3 = c3 - ((c3 - point) @ normal) * normal
    if opening.get("hinge") is not None:
        hinge = np.asarray(opening["hinge"], np.float64)
    else:                                  # borde trasero del corte
        back = pts[np.argmin(pts[:, 2])]
        hinge = np.array([c3[0], back[1], back[2]])
    fixed = _hollow(Va, lower, ring, c3, -normal)
    moving = _hollow(Va, upper, ring, c3, normal)
    angle = _angle(Va[np.unique(upper)], hinge, normal)
    return fixed, moving, tuple(float(x) for x in hinge), tuple(AXIS.tolist()), angle
