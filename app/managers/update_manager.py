from PySide6.QtCore import QThread, Signal

from app.utils.logger_util import get_logger
from app.utils.paths_util import IS_FROZEN
from app.utils.update_util import check_for_update, perform_update

log = get_logger("UPDATE_MANAGER")


class UpdateWorker(QThread):
    """Comprueba y aplica la actualización en segundo plano; la interfaz solo escucha las señales."""
    update_found = Signal(str, str)   # versión local, versión remota
    progress = Signal(float, str)     # 0..1, texto
    restart = Signal()                # todo listo: la app debe cerrarse para que el script reemplace los archivos
    failed = Signal(str)
    done = Signal()                   # no hay (o no se pudo aplicar) actualización: continuar con la app

    def run(self):
        try:
            info = check_for_update()
            if info is None:
                self.done.emit()
                return
            if not IS_FROZEN:
                log.info(f"Actualización {info.remote} disponible; omitida en modo desarrollo.")
                self.done.emit()
                return
            self.update_found.emit(info.local, info.remote)
            perform_update(lambda f, m: self.progress.emit(f, m))
            self.restart.emit()
        except Exception as e:
            log.error(f"Fallo en la actualización: {e}", exc_info=True)
            self.failed.emit(str(e))
