import numpy as np
from PySide6.QtCore import QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap, QPolygonF, QTransform
from PySide6.QtWidgets import QWidget

from app.gui.theme import COLORS
from app.shape.render import Scene


def texture_brush(model):
    """Pincel con la textura del modelo (o None si no tiene)."""
    tex = model.texture
    if tex is None:
        return None
    data = np.ascontiguousarray(tex)
    return QBrush(QImage(data.data, data.shape[1], data.shape[0], data.shape[1] * 4, QImage.Format_RGBA8888).copy())


def draw_bones(p, scene, yaw, pitch, zoom, open_t, width, height, pose=None):
    """Huesos (líneas) y articulaciones (puntos) encima del modelo."""
    lines, points = scene.joint_lines(yaw, pitch, zoom, open_t, width, height, pose)
    p.setPen(QPen(QColor(255, 196, 0), 2.0))
    for a, b in lines:
        p.drawLine(QPointF(*a), QPointF(*b))
    p.setPen(QPen(QColor(20, 20, 30), 1.0))
    p.setBrush(QColor(255, 255, 255))
    for x, y in points:
        p.drawEllipse(QPointF(x, y), 3.5, 3.5)


def draw_scene(p, scene, brush, yaw, pitch, zoom, open_t, width, height, wireframe=False, pose=None):
    """Dibuja un Scene con el pintor dado (lo usan el visor y las miniaturas)."""
    d = scene.draw_list(yaw, pitch, zoom, open_t, width, height, pose)
    polys, flat, shade, textured, coef = d["polys"], d["flat"], d["shade"], d["textured"], d["coef"]
    p.setPen(QPen(QColor(10, 12, 20, 200), 0.8) if wireframe else Qt.NoPen)
    for i in range(len(polys)):
        poly = QPolygonF([QPointF(x, y) for x, y in polys[i]])
        if textured[i] and brush is not None:
            a, b, c = coef[i, :, 0]
            dd, e, f = coef[i, :, 1]
            brush.setTransform(QTransform(a, dd, b, e, c, f))
            p.setBrush(brush)
            p.drawPolygon(poly)
            alpha = int((1.0 - shade[i]) * 255)
            if alpha > 0:  # sombreado: velo negro más o menos opaco
                p.setBrush(QColor(0, 0, 0, alpha))
                p.drawPolygon(poly)
        else:
            p.setBrush(QColor(*flat[i]))
            p.drawPolygon(poly)


def render_thumbnail(model, max_side: int = 64, yaw: float = 0.5, pitch: float = 0.25, size: int = 192):
    """Miniatura del modelo con fondo transparente, recortada a lo que ocupa el objeto y reducida a 'max_side' px."""
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    draw_scene(p, Scene(model), texture_brush(model), yaw, pitch, 1.0, 0.0, size, size)
    p.end()
    alpha = np.frombuffer(image.constBits(), np.uint8).reshape(size, image.bytesPerLine() // 4, 4)[:, :size, 3]
    ys, xs = np.where(alpha > 8)
    if len(xs):
        image = image.copy(QRect(int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)))
    return QPixmap.fromImage(image).scaled(max_side, max_side, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class MeshViewer(QWidget):
    """Visor ligero por software: texturas, apertura de piezas, rotación con ratón y zoom con rueda."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(420, 320)
        self.wireframe = False
        self.open_t = 0.0
        self.animate = False       # movimiento de prueba del esqueleto
        self.bones = False         # dibuja los huesos encima
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
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
            self._brush = texture_brush(model)
        self.update()

    def set_open(self, t: float):
        self.open_t = t
        self.update()

    def set_animate(self, on: bool):
        self.animate = on
        if on:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def set_bones(self, on: bool):
        self.bones = on
        self.update()

    def _tick(self):
        self._phase += 0.12
        self.update()

    def _pose(self):
        return self._scene.pose(self._phase) if self.animate and self._scene is not None else None

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

        pose = self._pose()
        draw_scene(p, self._scene, self._brush, self.yaw, self.pitch, self.zoom, self.open_t, self.width(), self.height(),
                   self.wireframe, pose)
        if self.bones:
            draw_bones(p, self._scene, self.yaw, self.pitch, self.zoom, self.open_t, self.width(), self.height(), pose)
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
