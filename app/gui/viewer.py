import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPolygonF, QTransform
from PySide6.QtWidgets import QWidget

from app.gui.theme import COLORS
from app.shape.render import Scene


class MeshViewer(QWidget):
    """Visor ligero por software: texturas, apertura de piezas, rotación con ratón y zoom con rueda."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(420, 320)
        self.wireframe = False
        self.open_t = 0.0
        self._scene = None
        self._brush = None
        self._last = None
        self._reset_view()

    def _reset_view(self):
        self.yaw, self.pitch, self.zoom = 0.5, 0.25, 1.0

    def set_model(self, model):
        self._scene, self._brush = None, None
        if model is not None:
            self._scene = Scene(model)
            tex = model.texture
            if tex is not None:
                data = np.ascontiguousarray(tex)
                image = QImage(data.data, data.shape[1], data.shape[0], data.shape[1] * 4, QImage.Format_RGBA8888).copy()
                self._brush = QBrush(image)
        self.update()

    def set_open(self, t: float):
        self.open_t = t
        self.update()

    def set_wireframe(self, on: bool):
        self.wireframe = on
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(COLORS["surface"]))
        if self._scene is None:
            p.setPen(QColor(COLORS["muted"]))
            p.drawText(self.rect(), Qt.AlignCenter, "El modelo aparecerá aquí")
            return

        d = self._scene.draw_list(self.yaw, self.pitch, self.zoom, self.open_t, self.width(), self.height())
        polys, flat, shade, textured, coef = d["polys"], d["flat"], d["shade"], d["textured"], d["coef"]
        p.setPen(QPen(QColor(10, 12, 20, 200), 0.8) if self.wireframe else Qt.NoPen)
        for i in range(len(polys)):
            poly = QPolygonF([QPointF(x, y) for x, y in polys[i]])
            if textured[i] and self._brush is not None:
                a, b, c = coef[i, :, 0]
                dd, e, f = coef[i, :, 1]
                self._brush.setTransform(QTransform(a, dd, b, e, c, f))
                p.setBrush(self._brush)
                p.drawPolygon(poly)
                alpha = int((1.0 - shade[i]) * 255)
                if alpha > 0:  # sombreado: velo negro más o menos opaco
                    p.setBrush(QColor(0, 0, 0, alpha))
                    p.drawPolygon(poly)
            else:
                p.setBrush(QColor(*flat[i]))
                p.drawPolygon(poly)

        p.setPen(QColor(COLORS["muted"]))
        p.drawText(12, self.height() - 12, "Arrastra para rotar · rueda para zoom · doble clic para restablecer")

    def mousePressEvent(self, e):
        self._last = e.position()

    def mouseMoveEvent(self, e):
        if self._last is None:
            return
        delta = e.position() - self._last
        self._last = e.position()
        self.yaw += delta.x() * 0.01
        self.pitch = max(-1.5, min(1.5, self.pitch + delta.y() * 0.01))
        self.update()

    def mouseReleaseEvent(self, _):
        self._last = None

    def mouseDoubleClickEvent(self, _):
        self._reset_view()
        self.update()

    def wheelEvent(self, e):
        self.zoom = max(0.3, min(6.0, self.zoom * 1.1 ** (e.angleDelta().y() / 120)))
        self.update()
