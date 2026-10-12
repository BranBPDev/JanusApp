from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from app.gui.widgets import icon_button, make_card, page_layout, set_thumbnail
from app.shape.project import ProjectInfo, list_projects

COLUMNS = 3
THUMB = 84


def _date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return "-"


class ProjectCard(QFrame):
    """Tarjeta de un proyecto local con su miniatura y el lápiz para editarlo."""

    def __init__(self, info: ProjectInfo, on_edit):
        super().__init__(objectName="Card")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 12, 12, 12)
        row.setSpacing(12)

        thumb = QLabel(objectName="Thumb")
        thumb.setFixedSize(THUMB, THUMB)
        thumb.setAlignment(Qt.AlignCenter)
        set_thumbnail(thumb, info.thumbnail, THUMB - 4)
        row.addWidget(thumb)

        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(QLabel(info.name, objectName="Brand"))
        opens = " · se abre" if info.openable else ""
        text.addWidget(QLabel(f"{info.triangles:,} triángulos{opens}", objectName="Muted"))
        text.addWidget(QLabel(_date(info.updated), objectName="Muted"))
        text.addStretch()
        row.addLayout(text, 1)

        edit = icon_button("edit", "#8A90A6", "IconEdit", "Editar las vistas y volver a generar", size=30)
        edit.clicked.connect(lambda: on_edit(info.name))
        row.addWidget(edit, 0, Qt.AlignTop)


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

        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        self.grid.setAlignment(Qt.AlignTop)
        holder = QWidget()
        holder.setLayout(self.grid)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        lay.addWidget(scroll, 1)
        self.refresh()

    def refresh(self):
        """Vuelve a leer los proyectos guardados en local."""
        while self.grid.count():
            self.grid.takeAt(0).widget().deleteLater()
        projects = list_projects()
        self.empty.setVisible(not projects)
        for i, info in enumerate(projects):
            self.grid.addWidget(ProjectCard(info, self.edit_requested.emit), i // COLUMNS, i % COLUMNS)
        for c in range(COLUMNS):
            self.grid.setColumnStretch(c, 1)
