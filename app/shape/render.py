import math

import numpy as np

from app.shape.rig.skeleton import pose_frames, skin_vertices, swing_rotations

_LIGHT = np.array([-0.4, 0.6, 0.7]) / np.linalg.norm([-0.4, 0.6, 0.7])
_DEFAULT = np.array([170.0, 178.0, 214.0])


def rotation(axis, degrees):
    a = np.array(axis, np.float64)
    a /= np.linalg.norm(a)
    t = math.radians(degrees)
    k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * k + (1 - math.cos(t)) * (k @ k)


class Scene:
    """Cálculo (sin Qt) de lo que dibuja el visor: pose de apertura, orden de profundidad y sombreado."""

    def __init__(self, model):
        self.model = model
        self.parts = model.parts
        self.by_name = {p.name: p for p in self.parts}
        self.faces = np.concatenate([p.faces + off for p, off in zip(self.parts, self._offsets())])
        self.base_color = self._face_colors()
        self.face_uv = self._face_uvs()
        all_v = np.concatenate([self.posed(0.0)[0], self.posed(1.0)[0]])  # encuadre válido cerrado y abierto
        self.center = (all_v.min(axis=0) + all_v.max(axis=0)) / 2
        self.radius = float(np.linalg.norm(all_v - self.center, axis=1).max()) or 1.0
        # caras interiores/bordes (UV constante): se dibujan "más lejos" para que el orden por profundidad no las cuele
        flat_uv = np.zeros(len(self.faces), bool) if self.face_uv is None else \
            np.abs(self.face_uv - self.face_uv[:, :1]).max(axis=(1, 2)) < 1e-6
        self.depth_bias = np.where(flat_uv, -0.02 * self.radius, 0.0)

    def _offsets(self):
        off, out = 0, []
        for p in self.parts:
            out.append(off)
            off += len(p.vertices)
        return out

    def _face_uvs(self):
        """UV de cada triángulo en píxeles de textura (m,3,2), o None si no hay textura."""
        tex = self.model.texture
        if tex is None or any(p.uvs is None for p in self.parts):
            return None
        h, w = tex.shape[:2]
        return np.concatenate([p.uvs[p.faces] for p in self.parts]).astype(np.float64) * np.array([w, h])

    def _face_colors(self):
        tex = self.model.texture
        colors = []
        for p in self.parts:
            if tex is None or p.uvs is None:
                colors.append(np.tile(_DEFAULT, (len(p.faces), 1)))
                continue
            uv = p.uvs[p.faces].mean(axis=1)
            h, w = tex.shape[:2]
            x = np.clip((uv[:, 0] * w).astype(int), 0, w - 1)
            y = np.clip((uv[:, 1] * h).astype(int), 0, h - 1)
            colors.append(tex[y, x, :3].astype(np.float64))
        return np.concatenate(colors)

    def pose(self, phase: float):
        """Pose de prueba del esqueleto (movimiento genérico) para la fase dada, o None si el modelo no tiene esqueleto."""
        sk = self.model.skeleton
        return None if sk is None else pose_frames(sk, swing_rotations(sk, phase))

    def joint_lines(self, yaw, pitch, zoom, t, width, height, pose=None):
        """Segmentos (padre -> hijo) de los huesos en pantalla, (k,2,2), y los puntos de las articulaciones (n,2)."""
        sk = self.model.skeleton
        if sk is None:
            return np.zeros((0, 2, 2)), np.zeros((0, 2))
        pts = (pose_frames(sk)[1] if pose is None else pose[1]) - self.center
        cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
        rot = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        vr = pts @ rot.T
        scale = min(width, height) * 0.42 / self.radius * zoom
        scr = np.stack([width / 2 + vr[:, 0] * scale, height / 2 - vr[:, 1] * scale], axis=1)
        links = [(p, i) for i, p in enumerate(sk.parents) if p >= 0]
        return (np.array([[scr[p], scr[i]] for p, i in links]) if links else np.zeros((0, 2, 2))), scr

    def posed(self, t: float, pose=None):
        """Vértices y normales con la apertura t (0 = cerrado, 1 = abierto) y, si se da, la pose del esqueleto."""
        verts, norms = [], []
        for p in self.parts:
            V, N = p.vertices.astype(np.float64), p.normals.astype(np.float64)
            if pose is not None and p.joints is not None:
                V, N = skin_vertices(V, N, p.joints, p.weights.astype(np.float64), self.model.skeleton, pose)
            node = p
            while node is not None:
                if node.axis is not None and t > 0:
                    R = rotation(node.axis, node.open_angle * t)
                    o = np.array(node.origin, np.float64)
                    V, N = (V - o) @ R.T + o, N @ R.T
                node = self.by_name.get(node.parent)
            verts.append(V)
            norms.append(N)
        return np.concatenate(verts), np.concatenate(norms)

    def draw_list(self, yaw, pitch, zoom, t, width, height, pose=None):
        V, N = self.posed(t, pose)
        V = V - self.center
        cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
        rot = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        vr, nr = V @ rot.T, N @ rot.T
        f = self.faces
        geo = np.cross(vr[f[:, 1]] - vr[f[:, 0]], vr[f[:, 2]] - vr[f[:, 0]])
        vis = np.nonzero(geo[:, 2] > 0)[0]
        order = vis[np.argsort(vr[f[vis], 2].mean(axis=1) + self.depth_bias[vis])]  # de lejos a cerca
        shade = 0.4 + 0.6 * np.clip(nr[f[order]].mean(axis=1) @ _LIGHT, 0, 1)
        scale = min(width, height) * 0.42 / self.radius * zoom
        sx = width / 2 + vr[:, 0] * scale
        sy_ = height / 2 - vr[:, 1] * scale
        tri = f[order]
        scr = np.stack([sx[tri], sy_[tri]], axis=2)            # (k,3,2)
        flat = np.clip(self.base_color[order] * shade[:, None], 0, 255).astype(int)
        coef, textured = None, np.zeros(len(order), bool)
        if self.face_uv is not None:
            uv = self.face_uv[order]
            m = np.concatenate([uv, np.ones((len(order), 3, 1))], axis=2)
            textured = np.abs(np.linalg.det(m)) > 1e-6
            coef = np.zeros((len(order), 3, 2))
            if textured.any():
                coef[textured] = np.linalg.solve(m[textured], scr[textured])
        # se agranda cada triángulo ~0.7 px para que no queden rendijas entre vecinos
        c = scr.mean(axis=1, keepdims=True)
        d = scr - c
        grown = c + d * (1 + 0.7 / np.maximum(np.linalg.norm(d, axis=2, keepdims=True), 1.0))
        return {"polys": grown, "flat": flat, "shade": shade, "textured": textured, "coef": coef}
