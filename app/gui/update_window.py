from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QProgressBar, QVBoxLayout, QWidget

from app.utils.paths_util import LOGO_PNG

_STEPS = 1000


class UpdateWindow(QWidget):
    """Ventana de arranque: comprueba actualizaciones y muestra el progreso de la descarga."""

    def __init__(self):
        super().__init__()
        self._can_close = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(440, 300)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame(objectName="UpdateCard")
        outer.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(36, 32, 36, 28)
        lay.setSpacing(6)

        logo = QLabel(alignment=Qt.AlignCenter)
        pix = QPixmap(str(LOGO_PNG))
        if not pix.isNull():
            logo.setPixmap(pix.scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(logo)

        title = QLabel("Janus", objectName="Title", alignment=Qt.AlignCenter)
        lay.addWidget(title)

        self.status = QLabel("Comprobando actualizaciones...", objectName="Subtitle", alignment=Qt.AlignCenter)
        lay.addSpacing(10)
        lay.addWidget(self.status)

        self.bar = QProgressBar(textVisible=False)
        self.bar.setRange(0, 0)  # indeterminada
        lay.addSpacing(8)
        lay.addWidget(self.bar)

        self.detail = QLabel("", objectName="Muted", alignment=Qt.AlignCenter)
        lay.addWidget(self.detail)
        lay.addStretch()

        self._center()

    def _center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def show_update(self, local: str, remote: str):
        self.status.setText(f"Actualizando a la versión {remote}")
        self.detail.setText(f"Versión actual: {local}")
        self.bar.setRange(0, _STEPS)
        self.bar.setValue(0)

    def set_progress(self, fraction: float, message: str):
        if self.bar.maximum() == 0:
            self.bar.setRange(0, _STEPS)
        self.bar.setValue(int(fraction * _STEPS))
        self.detail.setText(message)

    def finish(self):
        self._can_close = True
        self.close()

    def closeEvent(self, event):
        # Evita cerrar la ventana (y la app) mientras se actualiza.
        event.accept() if self._can_close else event.ignore()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.windowHandle():
            self.windowHandle().startSystemMove()
