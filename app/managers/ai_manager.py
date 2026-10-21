"""Hilos de la IA integrada: cargar el modelo y atender peticiones sin bloquear la interfaz."""
from PySide6.QtCore import QThread, Signal

from app.ai.assistant.asistente import Asistente
from app.ai.engine.generate import Cancelled
from app.shape.spec.schema import SpecError
from app.utils.logger_util import get_logger

log = get_logger("AI_MANAGER")


class LoadWorker(QThread):
    progress = Signal(float)
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            self.loaded.emit(Asistente(self.path, progress=self.progress.emit))
        except MemoryError:
            self.failed.emit("No hay RAM suficiente para este modelo. Prueba con un modelo más pequeño (por ejemplo, 0.5B).")
        except Exception as e:
            log.error(f"No se pudo cargar el modelo: {e}", exc_info=True)
            self.failed.emit(f"No se pudo cargar el modelo: {e}")


class AskWorker(QThread):
    tokens = Signal(int)
    done = Signal(object)       # asistente.Resultado
    failed = Signal(str)
    cancelled = Signal()
    stage = Signal(str)

    def __init__(self, assistant, text, spec, attachments=(), review=True):
        super().__init__()
        self.assistant, self.text, self.spec = assistant, text, spec
        self.attachments, self.review = list(attachments), review
        self._stop = False
        self._n = 0

    def stop(self):
        self._stop = True

    def _on_text(self, _piece):
        self._n += 1
        if self._n % 5 == 0:
            self.tokens.emit(self._n)

    def run(self):
        try:
            self.done.emit(self.assistant.pedir(self.text, self.spec, self.attachments, self._on_text, lambda: self._stop, self.review, self.stage.emit))
        except Cancelled:
            self.cancelled.emit()
        except SpecError as e:
            self.failed.emit(str(e))
        except Exception as e:
            log.error(f"Error de la IA: {e}", exc_info=True)
            self.failed.emit(f"Error de la IA: {e}")
