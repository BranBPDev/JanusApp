from PySide6.QtCore import QThread, Signal

from app.shape.pipeline import generate_shape
from app.shape.spec.blueprint import build_blueprint
from app.shape.spec.preview import build_preview
from app.shape.spec.schema import SpecError, load_spec
from app.shape.storage.project import save_shape
from app.utils.logger_util import get_logger

log = get_logger("SHAPE_MANAGER")


class _JsonWorker(QThread):
    """Hilo que trabaja con el JSON del objeto: los errores del JSON se muestran tal cual, los demás se registran."""
    failed = Signal(str)
    action = "procesando el objeto"

    def run(self):
        try:
            self.work()
        except SpecError as e:
            self.failed.emit(str(e))
        except Exception as e:
            log.error(f"Error {self.action}: {e}", exc_info=True)
            self.failed.emit(f"Error {self.action}: {e}")

    def work(self):
        raise NotImplementedError


class PreviewWorker(_JsonWorker):
    """Interpreta el JSON y dibuja la vista previa (vistas, cuadrícula con marcas, interiores) sin bloquear la interfaz."""
    done = Signal(object)    # {'name', 'size', 'views', 'grids', 'interiors', 'notes', 'bones', 'blueprint'}
    action = "dibujando la vista previa"

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def work(self):
        spec = load_spec(self.text)
        bp = build_blueprint(spec)
        self.done.emit(build_preview(spec, bp) | {"blueprint": bp})


class ShapeWorker(_JsonWorker):
    """Calcula la forma 3D a partir del JSON y la guarda en el proyecto sin bloquear la interfaz."""
    progress = Signal(float, str)
    finished_ok = Signal(object, str)   # ShapeResult, carpeta del proyecto
    action = "generando la forma"

    def __init__(self, name: str, spec_text: str, blueprint=None):
        super().__init__()
        self.name, self.spec_text, self.blueprint = name, spec_text, blueprint

    def work(self):
        bp = self.blueprint
        if bp is None:
            self.progress.emit(0.01, "Interpretando el JSON...")
            bp = build_blueprint(load_spec(self.spec_text))
        result = generate_shape(bp, lambda f, m: self.progress.emit(0.04 + 0.9 * f, m))
        self.progress.emit(0.95, "Guardando proyecto...")
        root = save_shape(self.name, result, self.spec_text)
        log.info(f"Forma generada en {root}: {result.info}")
        self.progress.emit(1.0, "Completado")
        self.finished_ok.emit(result, str(root))
