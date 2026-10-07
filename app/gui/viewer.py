import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from app.gui.theme import COLORS

_LEVELS = 24
_BASE = (170, 178, 214)
_LIGHT = np.array([-0.4, 0.6, 0.7]) / np.linalg.norm([-0.4, 0.6, 0.7])


class MeshViewer(QWidget):
    """Visor ligero por software (sombreado plano, rotación con ratón, zoom con rueda)."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(420, 320)
        self.wireframe = False
        self._mesh = None
        self._reset_view()
        self._last = None
        self._fills = [QColor(*(int(c * (0.25 + 0.75 * i / (_LEVELS - 1))) for c in _BASE)) for i in range(_LEVELS)]

    def _reset_view(self):
        self.yaw, self.pitch, self.zoom = 0.6, 0.25, 1.0

    def set_mesh(self, mesh):
        if mesh is None:
            self._mesh = None
        else:
            v = mesh.vertices.astype(np.float64)
            v = v - (v.min(axis=0) + v.max(axis=0)) / 2
            f = mesh.faces
            fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
            fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
            self._mesh = (v, f, fn, float(np.linalg.norm(v, axis=1).max()) or 1.0)
        self.update()

    def set_wireframe(self, on: bool):
        self.wireframe = on
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(COLORS["surface"]))
        if self._mesh is None:
            p.setPen(QColor(COLORS["muted"]))
            p.drawText(self.rect(), Qt.AlignCenter, "El modelo aparecerá aquí")
            return

        v, f, fn, radius = self._mesh
        cy, sy, cp, sp = np.cos(self.yaw), np.sin(self.yaw), np.cos(self.pitch), np.sin(self.pitch)
        ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
        rot = rx @ ry
        vr = v @ rot.T
        nr = fn @ rot.T

        w, h = self.width(), self.height()
        scale = min(w, h) * 0.42 / radius * self.zoom
        sx = (w / 2 + vr[:, 0] * scale).tolist()
        sy_ = (h / 2 - vr[:, 1] * scale).tolist()

        vis = np.nonzero(nr[:, 2] > 0)[0]
        order = vis[np.argsort(vr[f[vis], 2].mean(axis=1))]  # de lejos a cerca
        shade = np.clip(nr[order] @ _LIGHT, 0.0, 1.0)
        levels = (shade * (_LEVELS - 1)).astype(int).tolist()

        edge = QPen(QColor(10, 12, 20, 190), 0.8)
        tris = f[order].tolist()
        for tri, lv in zip(tris, levels):
            color = self._fills[lv]
            p.setBrush(color)
            p.setPen(edge if self.wireframe else QPen(color, 0.7))
            p.drawPolygon(QPolygonF([QPointF(sx[i], sy_[i]) for i in tri]))

        p.setPen(QColor(COLORS["muted"]))
        p.drawText(12, h - 12, "Arrastra para rotar · rueda para zoom · doble clic para restablecer")

    def mousePressEvent(self, e):
        self._last = e.position()

    def mouseMoveEvent(self, e):
        if self._last is None:
            return
        d = e.position() - self._last
        self._last = e.position()
        self.yaw += d.x() * 0.01
        self.pitch = max(-1.5, min(1.5, self.pitch + d.y() * 0.01))
        self.update()

    def mouseReleaseEvent(self, _):
        self._last = None

    def mouseDoubleClickEvent(self, _):
        self._reset_view()
        self.update()

    def wheelEvent(self, e):
        self.zoom = max(0.3, min(6.0, self.zoom * 1.1 ** (e.angleDelta().y() / 120)))
        self.update()
