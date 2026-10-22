from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget,
)

from app.gui.home_page import HomePage
from app.gui.shape_page import ShapePage
from app.gui.widgets import page_layout
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


class PlaceholderPage(QWidget):
    def __init__(self, title: str):
        super().__init__()
        lay = page_layout(self, title)
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
        self.pages = {}
        self.nav = QButtonGroup(self)
        self.nav.setExclusive(True)
        for index, (key, text) in enumerate(SECTIONS):
            button = QPushButton(text, objectName="NavButton", checkable=True)
            button.setCursor(Qt.PointingHandCursor)
            self.nav.addButton(button, index)
            side.addWidget(button)
            page = HomePage(info) if key == "home" else ShapePage() if key == "shape" else PlaceholderPage(text)
            self.pages[key] = page
            self.stack.addWidget(page)
        self.nav.idClicked.connect(self._show_section)
        self.nav.button(0).setChecked(True)
        self.pages["home"].edit_requested.connect(self._edit_project)
        self.pages["shape"].saved.connect(self.pages["home"].refresh)

        side.addStretch()
        side.addWidget(QLabel(f"v{info.get('version', '?')}", objectName="Muted"))

        main.addWidget(sidebar)
        main.addWidget(self.stack, 1)

        self.statusBar().showMessage("Listo")

    def closeEvent(self, e):
        self.pages["shape"].shutdown()
        super().closeEvent(e)

    def _show_section(self, index: int):
        self.stack.setCurrentIndex(index)
        if SECTIONS[index][0] == "home":
            self.pages["home"].refresh()

    def _edit_project(self, name: str):
        """Abre un proyecto existente en la pestaña Forma para cambiar sus vistas y volver a generarlo."""
        self.pages["shape"].load_project(name)
        self.nav.button([k for k, _ in SECTIONS].index("shape")).click()

    def notify(self, message: str, msec: int = 8000):
        self.statusBar().showMessage(message, msec)
