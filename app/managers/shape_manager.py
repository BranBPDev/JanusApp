from PySide6.QtCore import QThread, Signal

from app.shape.pipeline import ShapeParams, generate_shape
from app.shape.project import save_shape
from app.utils.logger_util import get_logger

log = get_logger("SHAPE_MANAGER")


class ShapeWorker(QThread):
    """Genera la forma 3D y la guarda en el proyecto sin bloquear la interfaz."""
    progress = Signal(float, str)
    finished_ok = Signal(object, str)   # ShapeResult, carpeta del proyecto
    failed = Signal(str)

    def __init__(self, name: str, view_paths: dict, grid_paths: dict, params: ShapeParams):
        super().__init__()
        self.name, self.view_paths, self.grid_paths, self.params = name, view_paths, grid_paths, params

    def run(self):
        try:
            result = generate_shape(self.view_paths, self.grid_paths, self.params, lambda f, m: self.progress.emit(f, m))
            self.progress.emit(0.95, "Guardando proyecto...")
            root = save_shape(self.name, self.view_paths, self.grid_paths, self.params, result)
            log.info(f"Forma generada en {root}: {result.info}")
            self.progress.emit(1.0, "Completado")
            self.finished_ok.emit(result, str(root))
        except Exception as e:
            log.error(f"Error generando la forma: {e}", exc_info=True)
            self.failed.emit(str(e))
