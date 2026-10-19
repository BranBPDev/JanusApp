from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QFrame, QLabel, QToolButton, QVBoxLayout, QWidget


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
