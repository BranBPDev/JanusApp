import numpy as np


def unique_edges(F: np.ndarray) -> np.ndarray:
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    e.sort(axis=1)
    key = e[:, 0].astype(np.int64) * (int(e.max()) + 1) + e[:, 1]
    _, idx = np.unique(key, return_index=True)
    return e[idx]


def compact(V: np.ndarray, F: np.ndarray):
    used = np.unique(F)
    remap = np.full(len(V), -1, np.int64)
    remap[used] = np.arange(len(used))
    return V[used], remap[F].astype(np.int32)


def remove_small_components(V, F, min_ratio: float = 0.02):
    """Elimina islas sueltas (menos del 2 % de las caras de la mayor)."""
    n = len(V)
    labels = np.arange(n)
    while True:
        fl = labels[F].min(axis=1)
        new = labels.copy()
        for k in range(3):
            np.minimum.at(new, F[:, k], fl)
        new = new[new]
        if np.array_equal(new, labels):
            break
        labels = new
    face_label = labels[F[:, 0]]
    ids, counts = np.unique(face_label, return_counts=True)
    keep = ids[counts >= counts.max() * min_ratio]
    return compact(V, F[np.isin(face_label, keep)])


def taubin_smooth(V: np.ndarray, F: np.ndarray, iters: int, lam: float = 0.5, mu: float = -0.53) -> np.ndarray:
    """Suavizado que no encoge el volumen."""
    if iters <= 0:
        return V
    n = len(V)
    e = unique_edges(F)
    a = np.concatenate([e[:, 0], e[:, 1]])
    b = np.concatenate([e[:, 1], e[:, 0]])
    deg = np.maximum(np.bincount(a, minlength=n), 1).astype(np.float64)
    V = V.astype(np.float64).copy()

    def laplacian(P):
        out = np.empty_like(P)
        for ax in range(3):
            out[:, ax] = np.bincount(a, weights=P[b, ax], minlength=n) / deg - P[:, ax]
        return out

    for _ in range(iters):
        V += lam * laplacian(V)
        V += mu * laplacian(V)
    return V


def vertex_normals(V: np.ndarray, F: np.ndarray) -> np.ndarray:
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V, dtype=np.float64)
    for k in range(3):
        for ax in range(3):
            N[:, ax] += np.bincount(F[:, k], weights=fn[:, ax], minlength=len(V))
    length = np.linalg.norm(N, axis=1, keepdims=True)
    return N / np.maximum(length, 1e-12)


def is_watertight(F: np.ndarray) -> bool:
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    e.sort(axis=1)
    key = e[:, 0].astype(np.int64) * (int(e.max()) + 1) + e[:, 1]
    return bool((np.unique(key, return_counts=True)[1] == 2).all())


def signed_volume(V: np.ndarray, F: np.ndarray) -> float:
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    return float(np.einsum("ij,ij->i", p0, np.cross(p1, p2)).sum() / 6.0)
