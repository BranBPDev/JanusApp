import os
import sys
import ctypes
from app.utils.logger_util import get_logger, install_excepthook, shutdown_logs

log = get_logger("SYSTEM")
APP_ID = "BranBP.JanusApp"


def main():
    log.info("--- INICIO DE APLICACIÓN ---")
    install_excepthook()

    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception as e:
            log.error(f"No se pudo establecer el AppUserModelID: {e}")

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from app.gui.theme import apply_theme
    from app.managers.app_manager import AppManager
    from app.utils.paths_util import APP_NAME, LOGO_ICO

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName(APP_NAME)
    qt_app.setWindowIcon(QIcon(str(LOGO_ICO)))
    apply_theme(qt_app)

    manager = AppManager(qt_app)
    manager.start()

    code = qt_app.exec()
    log.info(f"--- FIN DE APLICACIÓN (código {code}) ---")
    shutdown_logs()
    os._exit(code)  # cierre inmediato aunque haya un hilo de trabajo activo


if __name__ == "__main__":
    main()
