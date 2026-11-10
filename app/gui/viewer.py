import threading
import time

import numpy as np
from PySide6.QtCore import QPointF, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QWidget

from app.gui.theme import COLORS
from app.shape.render import Scene


def to_qimage(rgba):
    """QImage (RGBA premultiplicado) a partir de la matriz que devuelve Scene.render."""
    data = np.ascontiguousarray(rgba)
    return QImage(data.data, data.shape[1], data.shape[0], data.shape[1] * 4, QImage.Format_RGBA8888_Premultiplied).copy()


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


def draw_wire(p, scene, visible, yaw, pitch, zoom, open_t, width, height, pose=None):
    """Aristas de los triángulos visibles (sin las ocultas)."""
    P, _, _ = scene.screen(yaw, pitch, zoom, open_t, width, height, pose, 1)
    p.setPen(QPen(QColor(10, 12, 20, 200), 0.8))
    for a, b, c in P[visible]:
        p.drawPolygon(QPolygonF([QPointF(*a), QPointF(*b), QPointF(*c)]))


def render_thumbnail(model, max_side: int = 64, yaw: float = 0.5, pitch: float = 0.25, size: int = 192):
    """Miniatura del modelo con fondo transparente, recortada a lo que ocupa el objeto y reducida a 'max_side' px."""
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    img, _ = Scene(model).render(yaw, pitch, 1.0, 0.0, size, size, None, 2)
    p.drawImage(0, 0, to_qimage(img))
    p.end()
    alpha = np.frombuffer(image.constBits(), np.uint8).reshape(size, image.bytesPerLine() // 4, 4)[:, :size, 3]
    ys, xs = np.where(alpha > 8)
    if len(xs):
        image = image.copy(QRect(int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)))
    return QPixmap.fromImage(image).scaled(max_side, max_side, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class _Latest:
    """Hilo que solo ejecuta la última tarea pedida: las que no han empezado cuando llega otra se descartan."""

    def __init__(self, fn):
        self.fn = fn
        self._lock = threading.Lock()
        self._task = None
        self._busy = False

    def submit(self, *args):
        with self._lock:
            self._task = args
            if self._busy:
                return
            self._busy = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            with self._lock:
                task, self._task = self._task, None
                if task is None:
                    self._busy = False
                    return
            self.fn(*task)


class MeshViewer(QWidget):
    """Visor por software con z-buffer: texturas, apertura de piezas, rotación con ratón y zoom con rueda.
    Dos hilos independientes dibujan siempre la última vista pedida: uno rápido para seguir al ratón (su resolución se ajusta sola
    a lo que tarde el equipo, hasta la completa) y otro que, al parar, la repite con suavizado de bordes y se cancela si te mueves."""

    _done = Signal(object, object)
    FRAME = 0.09               # segundos que debe tardar como mucho un fotograma mientras se mueve

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
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(120)
        self._settle.timeout.connect(self._refine)
        self._done.connect(self._ready)
        self._scene = None
        self._last = None
        self._shown = None         # (clave, supermuestreo, imagen) de lo último calculado
        self._fast = _Latest(self._render)
        self._fine = _Latest(self._render)
        self._asked = {}           # hilo -> clave de la última petición
        self._cost = 0.0           # segundos por fotograma a resolución completa (media)
        self._reset_view()

    def _reset_view(self):
        self.yaw, self.pitch, self.zoom = 0.5, 0.25, 1.0

    def _key(self):
        return (self.yaw, self.pitch, self.zoom, self.open_t, self.width(), self.height(), round(self._phase, 4) if self.animate else None, id(self._scene))

    def _changed(self):
        self.update()

    def set_model(self, model):
        self._scene = Scene(model) if model is not None else None
        self._shown, self._asked = None, {}
        self._changed()

    def set_open(self, t: float):
        self.open_t = t
        self._changed()

    def set_animate(self, on: bool):
        self.animate = on
        if on:
            self._timer.start()
        else:
            self._timer.stop()
        self._changed()

    def set_bones(self, on: bool):
        self.bones = on
        self.update()

    def _tick(self):
        self._phase += 0.12
        self._changed()

    def _pose(self):
        return self._scene.pose(self._phase) if self.animate and self._scene is not None else None

    def set_wireframe(self, on: bool):
        self.wireframe = on
        self._changed()

    def _submit(self, worker, ss):
        """Pide dibujar la vista actual con supermuestreo ss (si no se había pedido ya)."""
        key = self._key()
        if self._asked.get(worker) == (key, ss):
            return
        self._asked[worker] = (key, ss)
        cancel = (lambda: self._key() != key) if ss > 1 else None
        worker.submit(key, self._scene, (self.yaw, self.pitch, self.zoom, self.open_t, self.width(), self.height()), self._pose(), ss, cancel)

    def _render(self, key, scene, view, pose, ss, cancel):
        start = time.perf_counter()
        img, _ = scene.render(*view, pose, ss, cancel)
        if img is not None:
            if ss <= 1:
                self._cost = (time.perf_counter() - start) / ss ** 2 if not self._cost else 0.6 * self._cost + 0.4 * (time.perf_counter() - start) / ss ** 2
            self._done.emit((key, ss), to_qimage(img))

    def _ready(self, tag, image):
        key, ss = tag
        if self._scene is None or key[-1] != id(self._scene) or (ss > 1 and key != self._key()):
            return
        self._shown = (key, ss, image)
        self.update()

    def _refine(self):
        """Al parar: la misma vista con suavizado de bordes."""
        if self._scene is not None and not self.animate and self._shown is not None and self._shown[0] == self._key():
            self._submit(self._fine, 1 if self._shown[1] < 1 else 2)

    def _draft_scale(self):
        """Resolución del fotograma rápido: la completa si el equipo la dibuja en FRAME segundos; si no, la que quepa."""
        return 1.0 if self._cost <= self.FRAME else max(0.35, (self.FRAME / self._cost) ** 0.5)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(COLORS["surface"]))
        if self._scene is None:
            p.setPen(QColor(COLORS["muted"]))
            p.drawText(self.rect(), Qt.AlignCenter, "El modelo aparecerá aquí")
            return
        key, pose = self._key(), self._pose()
        w, h = self.width(), self.height()
        if self.wireframe:
            img, visible = self._scene.render(self.yaw, self.pitch, self.zoom, self.open_t, w, h, pose, 1)
            p.drawImage(0, 0, to_qimage(img))
            draw_wire(p, self._scene, visible, self.yaw, self.pitch, self.zoom, self.open_t, w, h, pose)
        else:
            if self._shown is None or self._shown[0] != key:
                self._submit(self._fast, self._draft_scale())
            if self._shown is not None:
                p.drawImage(self.rect(), self._shown[2])
                if self._shown[0] == key and self._shown[1] < 2 and not self.animate:
                    self._settle.start()
        if self.bones:
            draw_bones(p, self._scene, self.yaw, self.pitch, self.zoom, self.open_t, w, h, pose)
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
        self._changed()

    def mouseReleaseEvent(self, _):
        self._last = None

    def mouseDoubleClickEvent(self, _):
        self._reset_view()
        self._changed()

    def wheelEvent(self, e):
        self.zoom = max(0.3, min(6.0, self.zoom * 1.1 ** (e.angleDelta().y() / 120)))
        self._changed()
