from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget,
)

from app.utils.paths_util import APP_NAME, LOGO_PNG
from app.utils.update_util import get_local_info

# (clave, texto) de cada sección. Las futuras fases se añaden aquí.
SECTIONS = [
    ("home", "Inicio"),
    ("shape", "Forma"),
    ("texture", "Texturas"),
    ("collision", "Colisión"),
    ("rig", "Esqueleto"),
    ("viewer", "Visor 3D"),
]


def make_card(title: str, value: str) -> QFrame:
    card = QFrame(objectName="Card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(20, 16, 20, 16)
    lay.setSpacing(4)
    lay.addWidget(QLabel(title, objectName="CardTitle"))
    lay.addWidget(QLabel(value, objectName="CardValue"))
    return card


class HomePage(QWidget):
    def __init__(self, info: dict):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 32, 36, 32)
        lay.setSpacing(6)
        lay.addWidget(QLabel("Bienvenido a Janus", objectName="Title"))
        lay.addWidget(QLabel("Conversión de vistas 2D en modelos 3D optimizados.", objectName="Subtitle"))
        lay.addSpacing(20)

        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(make_card("Versión", f"v{info.get('version', '?')}"))
        row.addWidget(make_card("Publicada", str(info.get("releaseDate", "-"))))
        row.addWidget(make_card("Autor", str(info.get("author", "-"))))
        lay.addLayout(row)
        lay.addStretch()


class PlaceholderPage(QWidget):
    def __init__(self, title: str):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 32, 36, 32)
        lay.addWidget(QLabel(title, objectName="Title"))
        lay.addStretch()
        lay.addWidget(QLabel("Próximamente", objectName="Subtitle", alignment=Qt.AlignCenter))
        lay.addStretch()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        info = get_local_info()
        self.setWindowTitle(f"{APP_NAME} v{info.get('version', '?')}")
        self.resize(1280, 800)
        self.setMinimumSize(1000, 650)

        root = QWidget(objectName="Root")
        self.setCentralWidget(root)
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # --- Barra lateral ---
        sidebar = QFrame(objectName="Sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 20, 14, 14)
        side.setSpacing(4)

        brand = QHBoxLayout()
        logo = QLabel()
        pix = QPixmap(str(LOGO_PNG))
        if not pix.isNull():
            logo.setPixmap(pix.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        brand.addWidget(logo)
        brand.addWidget(QLabel("Janus", objectName="Brand"))
        brand.addStretch()
        side.addLayout(brand)
        side.addSpacing(20)

        self.stack = QStackedWidget()
        self.nav = QButtonGroup(self)
        self.nav.setExclusive(True)
        for index, (key, text) in enumerate(SECTIONS):
            button = QPushButton(text, objectName="NavButton", checkable=True)
            button.setCursor(Qt.PointingHandCursor)
            self.nav.addButton(button, index)
            side.addWidget(button)
            self.stack.addWidget(HomePage(info) if key == "home" else PlaceholderPage(text))
        self.nav.idClicked.connect(self.stack.setCurrentIndex)
        self.nav.button(0).setChecked(True)

        side.addStretch()
        side.addWidget(QLabel(f"v{info.get('version', '?')}", objectName="Muted"))

        main.addWidget(sidebar)
        main.addWidget(self.stack, 1)

        self.statusBar().showMessage("Listo")

    def notify(self, message: str, msec: int = 8000):
        self.statusBar().showMessage(message, msec)
