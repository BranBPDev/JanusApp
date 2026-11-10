import math

import numpy as np

from app.shape.texture.sample import face_texels
from app.shape.zbuffer import shade, visibility, fragments
from app.shape.rig.skeleton import pose_frames, rotation_matrix, skin_vertices, swing_rotations

_LIGHT = np.array([-0.4, 0.6, 0.7]) / np.linalg.norm([-0.4, 0.6, 0.7])
_DEFAULT = np.array([170.0, 178.0, 214.0])


def rotation(axis, degrees):
    return rotation_matrix(axis, math.radians(degrees))


class Scene:
    """Cálculo (sin Qt) de lo que dibuja el visor: pose de apertura, orden de profundidad y sombreado."""

    def __init__(self, model):
        self.model = model
        self.parts = model.parts
        self.by_name = {p.name: p for p in self.parts}
        self.faces = np.concatenate([p.faces + off for p, off in zip(self.parts, self._offsets())])
        self.tex = self._reduced(model.texture)
        self.base_color = self._face_colors()
        self.face_alpha = self._face_alphas()
        self.face_uv = self._face_uvs()
        self.spread = self._spread()
        all_v = np.concatenate([self.posed(0.0)[0], self.posed(1.0)[0]])  # encuadre válido cerrado y abierto
        self.center = (all_v.min(axis=0) + all_v.max(axis=0)) / 2
        self.radius = float(np.linalg.norm(all_v - self.center, axis=1).max()) or 1.0

    @staticmethod
    def _reduced(tex, side=1024):
        """Textura reducida (promedio por bloques) para que al verla pequeña no parpadee."""
        if tex is None:
            return None
        k = max(1, max(tex.shape[:2]) // side)
        if k == 1:
            return tex
        h, w = tex.shape[0] // k * k, tex.shape[1] // k * k
        return tex[:h, :w].astype(np.float32).reshape(h // k, k, w // k, k, 4).mean(axis=(1, 3)).astype(np.uint8)

    def _spread(self):
        """Desplazamiento (con t = 1) de cada pieza suelta: se alejan del centro del conjunto para poder verlas por separado."""
        loose = [p for p in self.parts if p.independent]
        if len(loose) < 2:
            return {}
        origins = np.array([p.origin for p in loose], np.float64)
        v = np.concatenate([p.vertices for p in self.parts])
        dist = 0.35 * float((v.max(axis=0) - v.min(axis=0)).max())
        out = {}
        for i, (p, d) in enumerate(zip(loose, origins - origins.mean(axis=0))):
            norm = np.linalg.norm(d)
            out[p.name] = (d / norm if norm > 1e-9 else np.array([0.0, 1.0 if i else -1.0, 0.0])) * dist
        return out

    def _offsets(self):
        off, out = 0, []
        for p in self.parts:
            out.append(off)
            off += len(p.vertices)
        return out

    def _face_uvs(self):
        """UV de cada triángulo en píxeles de textura (m,3,2), o None si no hay textura."""
        tex = self.tex
        if tex is None or any(p.uvs is None for p in self.parts):
            return None
        h, w = tex.shape[:2]
        return np.concatenate([p.uvs[p.faces] for p in self.parts]).astype(np.float64) * np.array([w, h])

    def _face_colors(self):
        tex = self.tex
        colors = []
        for p in self.parts:
            if tex is None or p.uvs is None:
                colors.append(np.tile(_DEFAULT, (len(p.faces), 1)))
                continue
            colors.append(face_texels(tex, p.uvs, p.faces)[:, :3].astype(np.float64))
        return np.concatenate(colors)

    def _face_alphas(self):
        """Opacidad (0-1) de cada triángulo según el canal alfa de la textura (1 si no hay textura)."""
        tex = self.tex
        out = []
        for p in self.parts:
            if tex is None or p.uvs is None:
                out.append(np.ones(len(p.faces)))
                continue
            out.append(face_texels(tex, p.uvs, p.faces)[:, 3] / 255.0)
        return np.concatenate(out)

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
        """Vértices y normales con la apertura t (0 = cerrado/junto, 1 = abierto/separado) y, si se da, la pose del esqueleto."""
        verts, norms = [], []
        for p in self.parts:
            V, N = p.vertices.astype(np.float64), p.normals.astype(np.float64)
            if pose is not None and p.joints is not None:
                V, N = skin_vertices(V, N, p.joints, p.weights.astype(np.float64), self.model.skeleton, pose)
            if t > 0 and p.name in self.spread:
                V = V + self.spread[p.name] * t
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

    def screen(self, yaw, pitch, zoom, t, width, height, pose=None, ss=1):
        """Triángulos proyectados: pantalla (k,3,2) en píxeles de (width*ss, height*ss), profundidad (k,3) y normales (k,3,3) giradas."""
        V, N = self.posed(t, pose)
        V = V - self.center
        cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
        rot = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        vr, nr = V @ rot.T, N @ rot.T
        scale = min(width, height) * 0.42 / self.radius * zoom * ss
        sx = width * ss / 2 + vr[:, 0] * scale
        sy_ = height * ss / 2 - vr[:, 1] * scale
        f = self.faces
        scr = np.stack([sx[f], sy_[f]], axis=2)
        return scr, vr[f][:, :, 2], nr[f]

    def render(self, yaw, pitch, zoom, t, width, height, pose=None, ss=1, abort=None):
        """Imagen uint8 (alto,ancho,4) con alfa premultiplicado y fondo transparente, dibujada con z-buffer, y los triángulos visibles.
        ss > 1 (entero): supermuestreo con suavizado de bordes; ss < 1: borrador a menor resolución (la imagen es más pequeña).
        abort: función opcional; si devuelve True el dibujo se cancela y se devuelve (None, None)."""
        W, H = max(1, round(width * ss)), max(1, round(height * ss))
        P, Z, Nf = self.screen(yaw, pitch, zoom, t, width, height, pose, ss)
        geo = (P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1]) - (P[:, 2, 0] - P[:, 0, 0]) * (P[:, 1, 1] - P[:, 0, 1])
        back = geo > 0                                                     # eje y de pantalla hacia abajo: horario en pantalla = cara trasera
        Nf = np.where(back[:, None, None], -Nf, Nf)                        # caras opacas por las dos caras: la normal mira siempre a la cámara
        opaque = np.nonzero(self.face_alpha >= 0.999)[0]
        glass = np.nonzero((self.face_alpha < 0.999) & ~back)[0]
        color = np.zeros((W * H, 3))
        cover = np.zeros(W * H)
        zbuf, idbuf = visibility(P[opaque], Z[opaque], W, H, abort)
        if abort is not None and abort():
            return None, None
        pix = np.nonzero(idbuf >= 0)[0]
        if len(pix):
            tri = opaque[idbuf[pix]]
            col, _ = shade(P, tri, pix, W, Nf, self.face_uv, self.base_color, self.tex, _LIGHT)
            color[pix], cover[pix] = col, 1.0
        if len(glass):                                                     # cristal: capas de atrás adelante, mezcladas encima de lo opaco
            fp, fz, ft = [], [], []
            for p_, z_, t_ in fragments(P[glass], Z[glass], W, H):
                keep = z_ > zbuf[p_]
                fp.append(p_[keep]); fz.append(z_[keep]); ft.append(glass[t_[keep]])
            if fp and len(np.concatenate(fp)):
                fp, fz, ft = np.concatenate(fp), np.concatenate(fz), np.concatenate(ft)
                o = np.lexsort((fz, fp))
                fp, ft = fp[o], ft[o]
                first = np.ones(len(fp), bool)
                first[1:] = fp[1:] != fp[:-1]
                rank = np.arange(len(fp)) - np.maximum.accumulate(np.where(first, np.arange(len(fp)), 0))
                col, a = shade(P, ft, fp, W, Nf, self.face_uv, self.base_color, self.tex, _LIGHT)
                for r in range(int(rank.max()) + 1):
                    m = rank == r
                    pp, aa = fp[m], a[m]
                    color[pp] = col[m] * aa[:, None] + color[pp] * (1 - aa[:, None])
                    cover[pp] = aa + cover[pp] * (1 - aa)
        rgba = np.concatenate([color, cover[:, None] * 255], axis=1).reshape(H, W, 4)      # color ya va premultiplicado
        if ss > 1 and ss == int(ss):
            ss = int(ss)
            rgba = rgba.reshape(height, ss, width, ss, 4).mean(axis=(1, 3))
        visible = np.unique(opaque[idbuf[idbuf >= 0]])
        return np.clip(rgba + 0.5, 0, 255).astype(np.uint8), visible
