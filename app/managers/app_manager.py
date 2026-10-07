from PySide6.QtCore import QTimer

from app.gui.main_window import MainWindow
from app.gui.update_window import UpdateWindow
from app.managers.update_manager import UpdateWorker
from app.utils.logger_util import get_logger


class AppManager:
    def __init__(self, qt_app):
        self.log = get_logger("APP_MANAGER")
        self.qt_app = qt_app
        self.main_window = None
        self.update_window = UpdateWindow()
        self.worker = UpdateWorker()

        self.worker.update_found.connect(self.update_window.show_update)
        self.worker.progress.connect(self.update_window.set_progress)
        self.worker.restart.connect(self._on_restart)
        self.worker.failed.connect(lambda msg: self._open_main("No se pudo actualizar la aplicación."))
        self.worker.done.connect(lambda: self._open_main())

    def start(self):
        self.update_window.show()
        self.worker.start()

    def _open_main(self, notice: str = ""):
        if self.main_window:
            return
        self.log.info("Abriendo ventana principal.")
        self.main_window = MainWindow()
        self.main_window.show()
        if notice:
            self.main_window.notify(notice)
        self.update_window.finish()

    def _on_restart(self):
        self.log.info("Cerrando para completar la actualización.")
        self.update_window.set_progress(1.0, "Reiniciando aplicación...")
        QTimer.singleShot(1000, self.qt_app.quit)
