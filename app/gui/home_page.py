from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from app.gui.viewer import render_thumbnail
from app.gui.widgets import icon_button, make_card, page_layout
from app.shape.project import list_projects, load_model

THUMB = 64
_thumbs = {}   # (carpeta, fecha de modificación) -> miniatura ya renderizada


def _date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return "-"


def _thumbnail(info):
    key = (str(info.root), info.updated)
    if key not in _thumbs:
        model = load_model(info.root)
        _thumbs[key] = render_thumbnail(model, THUMB) if model is not None else None
    return _thumbs[key]


class HomePage(QWidget):
    edit_requested = Signal(str)   # nombre del proyecto que se quiere editar

    def __init__(self, info: dict):
        super().__init__()
        lay = page_layout(self, "Bienvenido a Janus", "Conversión de vistas 2D en modelos 3D optimizados.")
        lay.addSpacing(14)
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(make_card("Versión", f"v{info.get('version', '?')}"))
        row.addWidget(make_card("Publicada", str(info.get("releaseDate", "-"))))
        row.addWidget(make_card("Autor", str(info.get("author", "-"))))
        lay.addLayout(row)

        lay.addSpacing(18)
        lay.addWidget(QLabel("Proyectos", objectName="Title"))
        self.empty = QLabel("Aún no hay proyectos. Genera uno en la pestaña Forma.", objectName="Muted")
        lay.addWidget(self.empty)

        # Una sola lista que se rellena sola con los datos de los proyectos guardados; ocupa lo que ocupe su contenido.
        self.rows = QVBoxLayout()
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(0)
        self.list = QFrame(objectName="List")
        self.list.setLayout(self.rows)
        holder = QWidget()
        holder_lay = QVBoxLayout(holder)
        holder_lay.setContentsMargins(0, 0, 0, 0)
        holder_lay.addWidget(self.list)
        holder_lay.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        lay.addWidget(scroll, 1)
        self._pending = []
        self.refresh()

    def _add_row(self, info):
        row = QFrame(objectName="Row")
        h = QHBoxLayout(row)
        h.setContentsMargins(14, 8, 14, 8)
        h.setSpacing(14)

        thumb = QLabel()
        thumb.setFixedSize(THUMB, THUMB)
        thumb.setAlignment(Qt.AlignCenter)
        h.addWidget(thumb)

        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(QLabel(info.name, objectName="Brand"))
        opens = " · se abre" if info.openable else ""
        text.addWidget(QLabel(f"{info.triangles:,} triángulos{opens} · {_date(info.updated)}", objectName="Muted"))
        h.addLayout(text, 1)

        edit = icon_button("edit", "#8A90A6", "IconEdit", "Editar las vistas y volver a generar", size=30)
        edit.clicked.connect(lambda: self.edit_requested.emit(info.name))
        h.addWidget(edit)
        self.rows.addWidget(row)
        self._pending.append((thumb, info))

    def refresh(self):
        """Vuelve a leer los proyectos guardados en local y reconstruye la lista."""
        while self.rows.count():
            self.rows.takeAt(0).widget().deleteLater()
        self._pending = []
        projects = list_projects()
        self.empty.setVisible(not projects)
        self.list.setVisible(bool(projects))
        for info in projects:
            self._add_row(info)
        QTimer.singleShot(0, self._fill_next)   # las miniaturas se renderizan de una en una para no bloquear la ventana

    def _fill_next(self):
        if not self._pending:
            return
        thumb, info = self._pending.pop(0)
        try:
            pix = _thumbnail(info)
            if pix is not None:
                thumb.setPixmap(pix)
        except RuntimeError:   # la fila se ha destruido por un refresco
            pass
        QTimer.singleShot(0, self._fill_next)
