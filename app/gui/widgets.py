from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from app.shape.naming import IMAGE_FILTER, IMAGE_SUFFIXES

PREVIEW = 84


def icon(kind: str, color: str) -> QIcon:
    """Iconos de trazo simple (32x32): 'plus', 'trash' y 'edit' (lápiz)."""
    pm = QPixmap(32, 32)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(color), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    if kind == "plus":
        p.drawLine(16, 8, 16, 24)
        p.drawLine(8, 16, 24, 16)
    elif kind == "edit":
        p.drawPolyline(QPolygonF([QPointF(9, 23), QPointF(10, 18), QPointF(21, 7), QPointF(25, 11), QPointF(14, 22), QPointF(9, 23)]))
        p.drawLine(18, 10, 22, 14)
    else:  # papelera
        p.drawLine(8, 10, 24, 10)
        p.drawPolyline(QPolygonF([QPointF(13, 10), QPointF(13, 7), QPointF(19, 7), QPointF(19, 10)]))
        p.drawPolyline(QPolygonF([QPointF(10, 10), QPointF(11, 25), QPointF(21, 25), QPointF(22, 10)]))
        p.drawLine(14, 14, 14, 21)
        p.drawLine(18, 14, 18, 21)
    p.end()
    return QIcon(pm)


def icon_button(kind: str, color: str, name: str, tooltip: str, size: int = 24, parent=None) -> QToolButton:
    btn = QToolButton(parent, objectName=name)
    btn.setIcon(icon(kind, color))
    btn.setFixedSize(size, size)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setToolTip(tooltip)
    return btn


def page_layout(page: QWidget, title: str, subtitle: str = "", margins=(36, 32, 36, 32)) -> QVBoxLayout:
    """Cabecera estándar de página: título y subtítulo. Devuelve el layout para seguir añadiendo contenido."""
    lay = QVBoxLayout(page)
    lay.setContentsMargins(*margins)
    lay.setSpacing(6)
    lay.addWidget(QLabel(title, objectName="Title"))
    if subtitle:
        lay.addWidget(QLabel(subtitle, objectName="Subtitle"))
    return lay


def make_card(title: str, value: str) -> QFrame:
    card = QFrame(objectName="Card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(20, 16, 20, 16)
    lay.setSpacing(4)
    lay.addWidget(QLabel(title, objectName="CardTitle"))
    lay.addWidget(QLabel(value, objectName="CardValue"))
    return card


def set_thumbnail(label: QLabel, path, size: int):
    """Muestra una imagen escalada en un QLabel (o lo vacía si no hay imagen)."""
    pix = QPixmap(str(path)) if path else QPixmap()
    if pix.isNull():
        label.clear()
    else:
        label.setPixmap(pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))


class Preview(QLabel):
    """Cuadro de previsualización con un botón + (verde) y una papelera (roja) superpuestos."""

    def __init__(self):
        super().__init__(objectName="Thumb")
        self.path = None
        self.setFixedSize(PREVIEW, PREVIEW)
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)

        self.add_btn = icon_button("plus", "#22C55E", "IconAdd", "Elegir imagen", parent=self)
        self.add_btn.move(4, 4)
        self.add_btn.clicked.connect(self._pick)
        self.del_btn = icon_button("trash", "#EF4444", "IconDel", "Quitar imagen", parent=self)
        self.del_btn.move(PREVIEW - 28, 4)
        self.del_btn.clicked.connect(lambda: self.set_path(None))
        self._refresh()

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar imagen", "", IMAGE_FILTER)
        if path:
            self.set_path(path)

    def set_path(self, path):
        self.path = path
        self._refresh()

    def _refresh(self):
        set_thumbnail(self, self.path, PREVIEW - 4)
        self.del_btn.setVisible(bool(self.path))
        self.add_btn.raise_()
        self.del_btn.raise_()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if Path(p).suffix.lower() in IMAGE_SUFFIXES:
                self.set_path(p)
                break


class ViewPair(QFrame):
    """Dos imágenes con título y pie (por defecto: vista y malla)."""

    def __init__(self, title: str, captions=("Vista", "Malla")):
        super().__init__(objectName="Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(4)
        lay.addWidget(QLabel(title, objectName="Brand"))
        row = QHBoxLayout()
        row.setSpacing(8)
        self.view, self.grid = Preview(), Preview()
        for preview, caption in ((self.view, captions[0]), (self.grid, captions[1])):
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(preview)
            col.addWidget(QLabel(caption, objectName="CardTitle", alignment=Qt.AlignCenter))
            row.addLayout(col)
        lay.addLayout(row)

    def set_paths(self, first, second):
        self.view.set_path(first)
        self.grid.set_path(second)
