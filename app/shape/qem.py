import heapq
import numpy as np
from app.shape.mesh_ops import compact, unique_edges


def _vertex_quadrics(V, F):
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    c = np.cross(p1 - p0, p2 - p0)
    a2 = np.linalg.norm(c, axis=1)
    ok = a2 > 1e-14
    n = np.zeros_like(c)
    n[ok] = c[ok] / a2[ok, None]
    d = -(n * p0).sum(1)
    w = np.where(ok, a2 * 0.5, 0.0)
    comps = (n[:, 0] * n[:, 0], n[:, 0] * n[:, 1], n[:, 0] * n[:, 2], n[:, 0] * d, n[:, 1] * n[:, 1],
             n[:, 1] * n[:, 2], n[:, 1] * d, n[:, 2] * n[:, 2], n[:, 2] * d, d * d)
    Q = np.zeros((len(V), 10))
    for ci, comp in enumerate(comps):
        for k in range(3):
            Q[:, ci] += np.bincount(F[:, k], weights=comp * w, minlength=len(V))
    return Q, float(w.mean()) if len(w) else 0.0


def _err(q, x, y, z):
    return (q[0] * x * x + q[4] * y * y + q[7] * z * z
            + 2.0 * (q[1] * x * y + q[2] * x * z + q[5] * y * z + q[3] * x + q[6] * y + q[8] * z) + q[9])


def _best(q, pa, pb, eps):
    """Posición óptima de colapso y su coste (error cuádrico + pequeña penalización por longitud)."""
    mid = ((pa[0] + pb[0]) * 0.5, (pa[1] + pb[1]) * 0.5, (pa[2] + pb[2]) * 0.5)
    l2 = (pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2 + (pa[2] - pb[2]) ** 2
    cands = (tuple(pa), tuple(pb), mid)

    a2, ab, ac, ad, b2, bc, bd, c2, cd, _ = q
    det = a2 * (b2 * c2 - bc * bc) - ab * (ab * c2 - bc * ac) + ac * (ab * bc - b2 * ac)
    tr = a2 + b2 + c2
    if tr > 0.0 and abs(det) > 1e-6 * tr ** 3:
        r0, r1, r2 = -ad, -bd, -cd
        x = (r0 * (b2 * c2 - bc * bc) - ab * (r1 * c2 - bc * r2) + ac * (r1 * bc - b2 * r2)) / det
        y = (a2 * (r1 * c2 - bc * r2) - r0 * (ab * c2 - bc * ac) + ac * (ab * r2 - r1 * ac)) / det
        z = (a2 * (b2 * r2 - r1 * bc) - ab * (ab * r2 - r1 * ac) + r0 * (ab * bc - b2 * ac)) / det
        if (x - mid[0]) ** 2 + (y - mid[1]) ** 2 + (z - mid[2]) ** 2 <= 2.25 * l2:
            cands = ((x, y, z),)
    best, best_c = None, 0.0
    for p in cands:
        c = _err(q, p[0], p[1], p[2])
        if best is None or c < best_c:
            best, best_c = p, c
    return max(best_c, 0.0) + eps * l2, list(best)


def decimate(V: np.ndarray, F: np.ndarray, target_faces: int, progress=None):
    """Simplificación por colapso de aristas con error cuádrico (Garland-Heckbert)."""
    if len(F) <= target_faces:
        return V.copy(), F.copy()

    Qn, mean_area = _vertex_quadrics(V, F)
    eps = 1e-3 * mean_area
    P = V.astype(np.float64).tolist()
    Fl = F.tolist()
    Q = [tuple(r) for r in Qn.tolist()]
    n = len(P)
    vf = [set() for _ in range(n)]
    for fi, (a, b, c) in enumerate(Fl):
        vf[a].add(fi)
        vf[b].add(fi)
        vf[c].add(fi)

    alive = [True] * len(Fl)
    valive = [True] * n
    ver = [0] * n
    heap = []

    def push(a, b):
        if a > b:
            a, b = b, a
        q = tuple(x + y for x, y in zip(Q[a], Q[b]))
        cost, pos = _best(q, P[a], P[b], eps)
        heapq.heappush(heap, (cost, a, b, ver[a], ver[b], pos))

    def neighbors(v):
        s = set()
        for fi in vf[v]:
            s.update(Fl[fi])
        s.discard(v)
        return s

    for a, b in unique_edges(F).tolist():
        push(a, b)

    def flips(fi, a, b, pos):
        f = Fl[fi]
        p = [P[v] for v in f]
        q = [pos if (v == a or v == b) else P[v] for v in f]
        def normal(t):
            ux, uy, uz = t[1][0] - t[0][0], t[1][1] - t[0][1], t[1][2] - t[0][2]
            vx, vy, vz = t[2][0] - t[0][0], t[2][1] - t[0][1], t[2][2] - t[0][2]
            return uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        n0, n1 = normal(p), normal(q)
        l0 = (n0[0] ** 2 + n0[1] ** 2 + n0[2] ** 2) ** 0.5
        l1 = (n1[0] ** 2 + n1[1] ** 2 + n1[2] ** 2) ** 0.5
        if l1 < 1e-15:
            return True
        return (n0[0] * n1[0] + n0[1] * n1[1] + n0[2] * n1[2]) < 0.1 * l0 * l1

    faces_left = len(Fl)
    start = faces_left
    steps = 0
    while faces_left > target_faces and heap:
        cost, a, b, va, vb, pos = heapq.heappop(heap)
        if not (valive[a] and valive[b]) or ver[a] != va or ver[b] != vb:
            continue
        shared = vf[a] & vf[b]
        if not shared:
            continue
        na, nb = neighbors(a), neighbors(b)
        na.discard(b)
        nb.discard(a)
        if len(na & nb) != len(shared):  # evita crear geometría no-manifold
            continue
        if any(flips(fi, a, b, pos) for fi in (vf[a] | vf[b]) - shared):
            continue

        for fi in shared:
            alive[fi] = False
            for v in Fl[fi]:
                vf[v].discard(fi)
        faces_left -= len(shared)
        for fi in vf[b]:
            Fl[fi] = [a if v == b else v for v in Fl[fi]]
            vf[a].add(fi)
        vf[b] = set()
        valive[b] = False
        P[a] = pos
        Q[a] = tuple(x + y for x, y in zip(Q[a], Q[b]))
        ver[a] += 1
        for nb_v in neighbors(a):
            push(a, nb_v)

        steps += 1
        if progress and steps % 256 == 0:
            progress((start - faces_left) / max(1, start - target_faces))

    keep = [i for i, ok in enumerate(alive) if ok]
    return compact(np.asarray(P, np.float64), np.asarray([Fl[i] for i in keep], np.int32))
