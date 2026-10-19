"""Esqueletos: huesos del JSON -> articulaciones 3D -> pesos de piel -> pose.

Cada hueso del JSON ("marcas.huesos") tiene un id (0-59, un color de la PALETA en la vista previa), su padre (null = raíz)
y su posición en una o varias vistas (mismas coordenadas que el resto de marcas). La posición 3D sale de combinar las
vistas (frente/detrás: x,y · lados: z,y · arriba/abajo: x,z); lo que no se ve en ninguna vista se coloca a partir del
hueso padre o, si no hay, en el centro del volumen del objeto."""
import itertools
import math
from dataclasses import dataclass, field

import numpy as np

from app.shape.geometry.coords import VIEW_AXES, view_to_world

LEVELS = (125, 170, 215, 255)
PALETTE = np.array([c for c in itertools.product(LEVELS, repeat=3) if not (c[0] == c[1] == c[2])], np.int32)   # 60 colores
MAX_JOINTS = len(PALETTE)
INFLUENCES = 4          # huesos que pueden mover cada vértice
FALLOFF = 4.0           # cuanto mayor, más "duros" son los pesos lejos de las articulaciones
SMOOTH_PASSES = 3       # suavizado de los pesos sobre la superficie
REFINE_MIN = 0.12       # arista mínima junto a una articulación (fracción de la longitud media de los huesos)
REFINE_MAX = 0.6        # arista máxima en cualquier punto
REFINE_NEAR = 0.9       # la arista admitida crece con la distancia a la articulación más cercana
TIP = 0.6               # prolongación del último hueso de cada rama (fracción de su longitud)


# ---------------------------------------------------------------- esqueleto
@dataclass
class Skeleton:
    names: list
    parents: list           # índice del padre (-1 = raíz); los padres siempre van antes que sus hijos
    rest: np.ndarray        # (n,3) posición de cada articulación en reposo (espacio del modelo)
    ids: list = field(default_factory=list)    # número de articulación (color de la paleta) de cada hueso

    def __len__(self):
        return len(self.names)

    @property
    def children(self):
        out = [[] for _ in self.names]
        for i, p in enumerate(self.parents):
            if p >= 0:
                out[p].append(i)
        return out

    @property
    def depth(self):
        d = []
        for p in self.parents:
            d.append(0 if p < 0 else d[p] + 1)
        return d

    def scaled(self, s):
        return Skeleton(list(self.names), list(self.parents), np.asarray(self.rest, np.float64) * s, list(self.ids))

    def to_dict(self):
        return {"joints": [{"name": n, "id": i, "parent": None if p < 0 else self.names[p], "position": [round(float(v), 5) for v in r]}
                           for n, i, p, r in zip(self.names, self.ids, self.parents, self.rest)]}

    @staticmethod
    def from_dict(data):
        joints = data["joints"]
        index = {j["name"]: k for k, j in enumerate(joints)}
        return Skeleton([j["name"] for j in joints], [index[j["parent"]] if j["parent"] else -1 for j in joints],
                        np.array([j["position"] for j in joints], np.float64), [j.get("id", k) for k, j in enumerate(joints)])


def bone_name(joint_id: int) -> str:
    return f"bone_{joint_id:02d}"


def build_skeleton(per_view: dict, dims_m, depth_mid=None):
    """Combina las articulaciones de las vistas en un esqueleto 3D. Devuelve (Skeleton o None, avisos).
    'per_view' = {vista: [{'id', 'parent', 'x_m', 'y_m'}]} (Marks.joints); 'dims_m' = (ancho, alto, fondo) en metros; 'depth_mid(eje, pos)' devuelve el
    centro del volumen del objeto a lo largo de 'eje' para la posición (con NaN en los ejes desconocidos)."""
    warnings = []
    obs, parents = {}, {}
    for key, joints in per_view.items():
        for j in joints:
            world = view_to_world(key, j["x_m"], j["y_m"], dims_m)
            slot = obs.setdefault(j["id"], {0: [], 1: [], 2: []})
            for axis in VIEW_AXES[key]:
                slot[axis].append(float(world[axis]))
            parents.setdefault(j["id"], []).append(j["parent"])
    if not obs:
        return None, warnings
    if len(obs) > MAX_JOINTS:
        return None, [f"Demasiadas articulaciones marcadas ({len(obs)})."]

    tol = 0.03 * max(dims_m)
    raw = {}
    for jid, slot in obs.items():
        raw[jid] = np.array([np.mean(slot[a]) if slot[a] else np.nan for a in range(3)])
        if any(len(slot[a]) > 1 and max(slot[a]) - min(slot[a]) > tol for a in range(3)):
            warnings.append(f"La articulación {jid} no está en el mismo sitio en todas las vistas.")

    parent = {}
    for jid, plist in parents.items():
        votes = [q for q in plist if q is not None]
        if votes:
            best = max(set(votes), key=votes.count)
            if len(set(votes)) > 1:
                warnings.append(f"La articulación {jid} tiene padres distintos según la vista.")
            parent[jid] = best if best in obs and best != jid else None
            if best not in obs:
                warnings.append(f"La articulación {jid} apunta a un padre ({best}) que no está marcado.")
        else:
            parent[jid] = None
    roots = sorted(j for j, p in parent.items() if p is None)
    if not roots:
        return None, warnings + ["El esqueleto no tiene raíz: pon «padre»: null en el hueso principal."]
    for extra in roots[1:]:
        parent[extra] = roots[0]
        warnings.append(f"Hay varias raíces en el esqueleto: la articulación {extra} se une a la {roots[0]}.")
    for jid in list(parent):                       # ciclos
        seen, cur = {jid}, parent[jid]
        while cur is not None:
            if cur in seen:
                parent[jid] = roots[0]
                warnings.append(f"Ciclo en el esqueleto: la articulación {jid} se une a la {roots[0]}.")
                break
            seen.add(cur)
            cur = parent[cur]

    order, queue = [], [roots[0]]
    while queue:
        cur = queue.pop(0)
        order.append(cur)
        queue += sorted(j for j, p in parent.items() if p == cur)
    index = {j: k for k, j in enumerate(order)}
    pos = {}
    for jid in order:                               # lo que no se ve en ninguna vista: igual que el padre o centro del volumen
        p = raw[jid].copy()
        for a in range(3):
            if np.isnan(p[a]):
                q = pos.get(parent[jid])
                m = q[a] if q is not None else (depth_mid(a, p) if depth_mid else None)
                p[a] = m if m is not None and not np.isnan(m) else (dims_m[1] / 2 if a == 1 else 0.0)
        pos[jid] = p
    sk = Skeleton([bone_name(j) for j in order], [-1 if parent[j] is None else index[parent[j]] for j in order],
                  np.array([pos[j] for j in order], np.float64), list(order))
    return sk, warnings


def depth_finder(hull, lo, cell):
    """Función depth_mid para build_skeleton a partir de un volumen ocupado (bool [x,y,z]) con esquina 'lo' y celda 'cell'."""
    shape = np.array(hull.shape)

    def find(axis, p):
        idx = []
        for a in range(3):
            if a == axis:
                idx.append(slice(None))
            else:
                v = p[a]
                if np.isnan(v):
                    return None
                idx.append(int(np.clip((v - lo[a]) / cell[a], 0, shape[a] - 1)))
        line = np.nonzero(hull[tuple(idx)])[0]
        if not len(line):
            return None
        return lo[axis] + (line[0] + line[-1] + 1) / 2 * cell[axis]
    return find


# ---------------------------------------------------------------- pose
def rotation_matrix(axis, radians):
    a = np.asarray(axis, np.float64)
    a = a / max(np.linalg.norm(a), 1e-12)
    k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(radians) * k + (1 - math.cos(radians)) * (k @ k)


def pose_frames(sk, local=None):
    """Rotación y posición global de cada articulación. 'local' = (n,3,3) rotaciones locales (None = reposo)."""
    n = len(sk)
    Rg, pg = np.empty((n, 3, 3)), np.empty((n, 3))
    for i, p in enumerate(sk.parents):
        R = np.eye(3) if local is None else local[i]
        if p < 0:
            Rg[i], pg[i] = R, sk.rest[i]
        else:
            Rg[i] = Rg[p] @ R
            pg[i] = pg[p] + Rg[p] @ (sk.rest[i] - sk.rest[p])
    return Rg, pg


def skin_vertices(V, N, joints, weights, sk, frames):
    """Vértices y normales deformados por la pose (skinning lineal)."""
    Rg, pg = frames
    R = Rg[joints]                                  # (n,k,3,3)
    rel = V[:, None, :] - sk.rest[joints]
    pos = (np.einsum("nkij,nkj->nki", R, rel) + pg[joints]) * weights[..., None]
    nor = np.einsum("nkij,nj->nki", R, N) * weights[..., None]
    out_n = nor.sum(axis=1)
    return pos.sum(axis=1), out_n / np.maximum(np.linalg.norm(out_n, axis=1, keepdims=True), 1e-12)


def swing_pose(sk, phase):
    """Movimiento de prueba genérico a partir de la forma del esqueleto: las ramas verticales (patas) se balancean en
    diagonal y las horizontales (cola, columna) ondulan. Devuelve (ejes (n,3), ángulos (n,) en radianes)."""
    n = len(sk)
    axes, angles = np.tile([1.0, 0.0, 0.0], (n, 1)), np.zeros(n)
    depth = sk.depth
    root = sk.rest[0]
    span = max(float(np.ptp(sk.rest, axis=0).max()), 1e-6)
    for i in range(1, n):
        d = sk.rest[i] - sk.rest[sk.parents[i]]
        length = np.linalg.norm(d)
        if length < 1e-9:
            continue
        side = sk.rest[i, 0] - root[0]
        side = 0.0 if abs(side) < 0.04 * span else math.copysign(1.0, side)
        lag = depth[i] * 0.45
        if abs(d[1]) / length > 0.6:                # vertical: pata
            gait = math.pi * ((side > 0) + (sk.rest[i, 2] > root[2]) * (side != 0))
            axes[i], angles[i] = (1.0, 0.0, 0.0), math.radians(24) * math.sin(phase + lag + gait)
        else:                                       # horizontal: cola, columna, cuello
            axes[i], angles[i] = (0.0, 1.0, 0.0), math.radians(16) * math.sin(phase + lag)
    return axes, angles


def swing_rotations(sk, phase):
    axes, angles = swing_pose(sk, phase)
    return np.array([rotation_matrix(a, t) for a, t in zip(axes, angles)])


# ---------------------------------------------------------------- pesos de piel
def _segments(sk):
    """Segmentos que mueve cada articulación: hacia cada hijo; las puntas se prolongan un poco más allá."""
    kids = sk.children
    out = []
    for i in range(len(sk)):
        if kids[i]:
            out += [(i, sk.rest[i], sk.rest[c]) for c in kids[i]]
        else:
            p = sk.parents[i]
            d = sk.rest[i] - sk.rest[p] if p >= 0 else np.array([0.0, 1.0, 0.0])
            out.append((i, sk.rest[i], sk.rest[i] + d * TIP))
    return out


def skin_weights(V, F, sk):
    """Pesos de piel automáticos: cada vértice sigue a los huesos más cercanos (más cuanto más cerca) y los pesos se
    suavizan sobre la superficie, sin mezclar partes que no se tocan. Devuelve (joints (n,4) uint8, weights (n,4) float32)."""
    V = np.asarray(V, np.float64)
    n, J = len(V), len(sk)
    uniq, inv = np.unique(np.round(V * 1e5).astype(np.int64), axis=0, return_inverse=True)   # vértices soldados
    inv = inv.reshape(-1)
    P = np.zeros((len(uniq), 3))
    P[inv] = V
    dist = np.full((len(uniq), J), np.inf)
    for j, a, b in _segments(sk):
        ab = b - a
        t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
        dist[:, j] = np.minimum(dist[:, j], np.linalg.norm(P - (a + t[:, None] * ab), axis=1))
    lengths = [np.linalg.norm(sk.rest[i] - sk.rest[p]) for i, p in enumerate(sk.parents) if p >= 0]
    eps = 0.05 * (float(np.mean(lengths)) if lengths else 1.0)
    W = (((dist.min(axis=1, keepdims=True) + eps) / (dist + eps)) ** FALLOFF).astype(np.float32)

    edges = np.concatenate([inv[F][:, [0, 1]], inv[F][:, [1, 2]], inv[F][:, [2, 0]]])
    edges = np.unique(np.sort(edges, axis=1), axis=0)
    edges = edges[edges[:, 0] != edges[:, 1]]
    deg = np.bincount(np.concatenate([edges[:, 0], edges[:, 1]]), minlength=len(uniq)).astype(np.float32)
    for _ in range(SMOOTH_PASSES):
        acc = np.zeros_like(W)
        np.add.at(acc, edges[:, 0], W[edges[:, 1]])
        np.add.at(acc, edges[:, 1], W[edges[:, 0]])
        W = np.where(deg[:, None] > 0, 0.5 * W + 0.5 * acc / np.maximum(deg[:, None], 1), W)

    k = min(INFLUENCES, J)
    top = np.argsort(-W, axis=1)[:, :k]
    w = np.take_along_axis(W, top, axis=1)
    w /= np.maximum(w.sum(axis=1, keepdims=True), 1e-12)
    joints = np.zeros((len(uniq), INFLUENCES), np.uint8)
    weights = np.zeros((len(uniq), INFLUENCES), np.float32)
    joints[:, :k], weights[:, :k] = top, w
    return joints[inv], weights[inv]


def refine_mesh(V, F, sk, iterations=5):
    """Divide por la mitad las aristas largas que quedan cerca de las articulaciones (sin mover ningún vértice), para que
    el modelo se doble bien al moverse. Lejos de las articulaciones la malla se queda como está."""
    lengths = [np.linalg.norm(sk.rest[i] - sk.rest[p]) for i, p in enumerate(sk.parents) if p >= 0]
    mean = float(np.mean(lengths)) if lengths else 1.0
    lo, hi = REFINE_MIN * mean, REFINE_MAX * mean
    V, F = np.asarray(V, np.float64), np.asarray(F, np.int64)
    for _ in range(iterations):
        pairs = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
        edges, inv = np.unique(pairs, axis=0, return_inverse=True)
        inv = inv.reshape(-1)
        a, b = V[edges[:, 0]], V[edges[:, 1]]
        mid = (a + b) / 2
        near = np.min(np.linalg.norm(mid[:, None, :] - sk.rest[None], axis=2), axis=1)
        split = np.linalg.norm(a - b, axis=1) > np.clip(REFINE_NEAR * near, lo, hi)
        if not split.any():
            break
        new_index = np.full(len(edges), -1, np.int64)
        new_index[split] = len(V) + np.arange(int(split.sum()))
        V = np.vstack([V, mid[split]])
        m = new_index[inv].reshape(-1, 3, order="F")   # columnas: arista ab, bc, ca
        flag = m >= 0
        n = flag.sum(axis=1)
        out = [F[n == 0]]
        for count in (1, 2, 3):
            sel = np.nonzero(n == count)[0]
            if not len(sel):
                continue
            tri, mm, fl = F[sel], m[sel], flag[sel]
            if count == 1:       # girar para que la arista dividida sea ab
                r = np.argmax(fl, axis=1)
            elif count == 2:     # girar para que la arista sin dividir sea ca
                r = (np.argmin(fl, axis=1) + 1) % 3
            else:
                r = np.zeros(len(sel), int)
            idx = (np.arange(3)[None, :] + r[:, None]) % 3
            A, B, C = (np.take_along_axis(tri, idx, 1)[:, k] for k in range(3))
            mab, mbc, mca = (np.take_along_axis(mm, idx, 1)[:, k] for k in range(3))
            if count == 1:
                out += [np.stack([A, mab, C], 1), np.stack([mab, B, C], 1)]
            elif count == 2:
                out += [np.stack([A, mab, mbc], 1), np.stack([A, mbc, C], 1), np.stack([mab, B, mbc], 1)]
            else:
                out += [np.stack([A, mab, mca], 1), np.stack([B, mbc, mab], 1), np.stack([C, mca, mbc], 1),
                        np.stack([mab, mbc, mca], 1)]
        F = np.concatenate(out)
    return V, F.astype(np.int32)


def attach_skeleton(model, sk):
    """Devuelve el modelo con el esqueleto y los pesos de piel de todas sus piezas."""
    model.skeleton = sk
    for part in model.parts:
        part.joints, part.weights = skin_weights(part.vertices, part.faces, sk)
    return model
