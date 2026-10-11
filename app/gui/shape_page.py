import unicodedata
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QSlider, QToolButton, QVBoxLayout, QWidget,
)

from app.gui.viewer import MeshViewer
from app.managers.shape_manager import ShapeWorker

IMAGE_FILTER = "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp *.tga *.tif *.tiff)"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tga", ".tif", ".tiff"}
GRID_WORDS = ("malla", "grid", "mesh")
PREVIEW = 84

# (clave, título, palabras del nombre de archivo). Orden de la cuadrícula: 2 columnas x 3 filas.
VIEWS = (
    ("front", "Frente", ("front", "frente", "delante", "frontal")),
    ("back", "Detrás", ("back", "atras", "detras", "trasera", "posterior", "rear")),
    ("left", "Izquierda", ("left", "izq")),
    ("right", "Derecha", ("right", "der")),
    ("top", "Arriba", ("top", "arriba", "superior", "cenital")),
    ("bottom", "Abajo", ("bottom", "abajo", "inferior", "debajo")),
)


def _normalize(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def classify(filename: str):
    """(vista o None, es_malla) a partir del nombre del archivo. Ej.: 'pokeball_frente_malla.png' -> ('front', True)."""
    name = _normalize(Path(filename).stem)
    is_grid = any(w in name for w in GRID_WORDS)
    for key, _, words in sorted(VIEWS, key=lambda v: v[0] not in ("left", "right")):  # izquierda/derecha primero
        if any(w in name for w in words):
            return key, is_grid
    return None, is_grid


def object_name(paths) -> str:
    """Nombre del objeto: lo que queda del nombre del primer archivo al quitar la vista y 'malla'."""
    words = {w for _, _, ws in VIEWS for w in ws} | set(GRID_WORDS)
    for p in paths:
        tokens = [t for t in _normalize(Path(p).stem).replace("-", "_").replace(" ", "_").split("_")
                  if t and not any(t == w or t.startswith(w) for w in words)]
        if tokens:
            return "_".join(tokens)
    return "objeto"


def _icon(kind: str, color: str) -> QIcon:
    pm = QPixmap(32, 32)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(color), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    if kind == "plus":
        p.drawLine(16, 8, 16, 24)
        p.drawLine(8, 16, 24, 16)
    else:  # papelera
        p.drawLine(8, 10, 24, 10)
        p.drawPolyline(QPolygonF([QPointF(13, 10), QPointF(13, 7), QPointF(19, 7), QPointF(19, 10)]))
        p.drawPolyline(QPolygonF([QPointF(10, 10), QPointF(11, 25), QPointF(21, 25), QPointF(22, 10)]))
        p.drawLine(14, 14, 14, 21)
        p.drawLine(18, 14, 18, 21)
    p.end()
    return QIcon(pm)


class Preview(QLabel):
    """Cuadro de previsualización con un botón + (verde) y una papelera (roja) superpuestos."""

    def __init__(self):
        super().__init__(objectName="Thumb")
        self.path = None
        self.setFixedSize(PREVIEW, PREVIEW)
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)

        self.add_btn = QToolButton(self, objectName="IconAdd")
        self.add_btn.setIcon(_icon("plus", "#22C55E"))
        self.add_btn.setFixedSize(24, 24)
        self.add_btn.move(4, 4)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setToolTip("Elegir imagen")
        self.add_btn.clicked.connect(self._pick)

        self.del_btn = QToolButton(self, objectName="IconDel")
        self.del_btn.setIcon(_icon("trash", "#EF4444"))
        self.del_btn.setFixedSize(24, 24)
        self.del_btn.move(PREVIEW - 28, 4)
        self.del_btn.setCursor(Qt.PointingHandCursor)
        self.del_btn.setToolTip("Quitar imagen")
        self.del_btn.clicked.connect(lambda: self.set_path(None))
        self._refresh()

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar imagen", "", IMAGE_FILTER)
        if path:
            self.set_path(path)

    def set_path(self, path):
        self.path = path
        self._refresh()

    def _refresh(self):
        pix = QPixmap(self.path) if self.path else QPixmap()
        if pix.isNull():
            self.clear()
        else:
            self.setPixmap(pix.scaled(PREVIEW - 4, PREVIEW - 4, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.del_btn.setVisible(bool(self.path))
        self.add_btn.raise_()
        self.del_btn.raise_()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if Path(p).suffix.lower() in IMAGE_SUFFIXES:
                self.set_path(p)
                break


class ViewPair(QFrame):
    """Una vista (izquierda) y su malla (derecha)."""

    def __init__(self, title: str):
        super().__init__(objectName="Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(4)
        lay.addWidget(QLabel(title, objectName="Brand"))
        row = QHBoxLayout()
        row.setSpacing(8)
        self.view, self.grid = Preview(), Preview()
        for preview, caption in ((self.view, "Vista"), (self.grid, "Malla")):
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(preview)
            col.addWidget(QLabel(caption, objectName="CardTitle", alignment=Qt.AlignCenter))
            row.addLayout(col)
        lay.addLayout(row)


class ShapePage(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.result = None
        self.project_root = None
        self.pairs = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(20)

        # ---------- Panel izquierdo (sin scroll) ----------
        panel = QWidget()
        panel.setFixedWidth(410)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(QLabel("Generar objeto 3D", objectName="Title"))
        lay.addWidget(QLabel("Cada vista con su malla. Todo se calcula solo.", objectName="Subtitle"))

        grid = QGridLayout()
        grid.setSpacing(8)
        for i, (key, title, _) in enumerate(VIEWS):
            pair = ViewPair(title)
            self.pairs[key] = pair
            grid.addWidget(pair, i // 2, i % 2)
        lay.addLayout(grid)

        load = QPushButton("Cargar vistas y mallas...")
        load.setToolTip("Elige todas las imágenes a la vez. Se asignan por el nombre: pokeball_frente.png y pokeball_frente_malla.png.")
        load.clicked.connect(self._load_files)
        lay.addWidget(load)

        self.gen_btn = QPushButton("Generar modelo 3D", objectName="Primary")
        self.gen_btn.setCursor(Qt.PointingHandCursor)
        self.gen_btn.clicked.connect(self._generate)
        lay.addWidget(self.gen_btn)
        self.progress = QProgressBar(textVisible=False)
        self.progress.setRange(0, 1000)
        self.status = QLabel("", objectName="Muted")
        self.status.setWordWrap(True)
        lay.addWidget(self.progress)
        lay.addWidget(self.status)
        lay.addStretch()
        root.addWidget(panel)

        # ---------- Panel derecho ----------
        right = QVBoxLayout()
        right.setSpacing(10)
        self.viewer = MeshViewer()
        right.addWidget(self.viewer, 1)

        self.open_row = QWidget()
        orow = QHBoxLayout(self.open_row)
        orow.setContentsMargins(0, 0, 0, 0)
        orow.addWidget(QLabel("Apertura"))
        self.open_slider = QSlider(Qt.Horizontal)
        self.open_slider.setRange(0, 100)
        self.open_slider.valueChanged.connect(lambda v: self.viewer.set_open(v / 100))
        orow.addWidget(self.open_slider, 1)
        self.open_row.hide()
        right.addWidget(self.open_row)

        bar = QHBoxLayout()
        self.lod_group = QButtonGroup(self)
        self.lod_buttons = []
        for i in range(4):
            b = QPushButton(f"LOD{i}", objectName="Seg", checkable=True)
            b.setEnabled(False)
            self.lod_group.addButton(b, i)
            self.lod_buttons.append(b)
            bar.addWidget(b)
        self.lod_group.idClicked.connect(self._show_lod)
        bar.addStretch()
        wire = QCheckBox("Ver malla")
        wire.toggled.connect(self.viewer.set_wireframe)
        bar.addWidget(wire)
        self.open_btn = QPushButton("Abrir carpeta")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.project_root)))
        bar.addWidget(self.open_btn)
        right.addLayout(bar)

        self.info = QLabel("", objectName="Muted")
        self.info.setWordWrap(True)
        self.warn = QLabel("", objectName="Warn")
        self.warn.setWordWrap(True)
        self.warn.hide()
        right.addWidget(self.info)
        right.addWidget(self.warn)
        root.addLayout(right, 1)

    # ---------- Acciones ----------
    def _load_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Seleccionar vistas y mallas", "", IMAGE_FILTER)
        unknown = []
        for p in paths:
            key, is_grid = classify(p)
            if key is None:
                unknown.append(Path(p).name)
            else:
                (self.pairs[key].grid if is_grid else self.pairs[key].view).set_path(p)
        self.status.setText("Sin asignar (nombre no reconocido): " + ", ".join(unknown) if unknown else "")

    def _generate(self):
        views = {k: p.view.path for k, p in self.pairs.items()}
        grids = {k: p.grid.path for k, p in self.pairs.items()}
        if not views["front"] or not (views["left"] or views["right"]):
            self.status.setText("Se necesitan al menos la vista frontal y una vista lateral.")
            return
        missing = [t for (k, t, _) in VIEWS if views[k] and not grids[k]]
        if missing:
            self.status.setText("Falta la malla de: " + ", ".join(missing) + ".")
            return
        self.gen_btn.setEnabled(False)
        self.warn.hide()
        self.progress.setValue(0)
        self.worker = ShapeWorker(object_name([p for p in views.values() if p]), views, grids)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_progress(self, fraction, message):
        self.progress.setValue(int(fraction * 1000))
        self.status.setText(message)

    def _on_failed(self, message):
        self.gen_btn.setEnabled(True)
        self.progress.setValue(0)
        self.status.setText(f"Error: {message}")

    def _on_done(self, result, root):
        self.result, self.project_root = result, root
        self.gen_btn.setEnabled(True)
        self.open_btn.setEnabled(True)
        self.status.setText(f"Guardado en {root} ({result.info['seconds']} s)")
        for i, b in enumerate(self.lod_buttons):
            b.setEnabled(i < len(result.lods) and not result.descriptor)
        self.lod_buttons[0].setChecked(True)
        self.open_slider.setValue(0)
        self.open_row.setVisible(result.lods[0].openable)
        self._show_lod(0)
        if result.warnings:
            self.warn.setText("\n".join(result.warnings))
            self.warn.show()

    def _show_lod(self, index):
        model = self.result.lods[index]
        self.viewer.set_model(model)
        self.viewer.set_open(self.open_slider.value() / 100)
        w, h, d = model.size
        opens = " · se abre" if model.openable else ""
        if self.result.descriptor:
            kind = "Esfera" if self.result.descriptor["type"] == "sphere" else "Elipsoide"
            self.info.setText(
                f"{kind} paramétrico: 0 triángulos propios (el motor usa su {kind.lower()} compartida con esta textura)\n"
                f"{w:.2f} × {h:.2f} × {d:.2f} m · textura {self.result.texture.shape[1]}×{self.result.texture.shape[0]}{opens}\n"
                "La malla del visor es solo una vista previa y no se guarda.")
            return
        shape = "primitiva simple" if self.result.info.get("mode") == "primitiva" else "volumen de las vistas"
        tex = f" · textura {model.texture.shape[1]}×{model.texture.shape[0]}" if model.texture is not None else ""
        self.info.setText(
            f"LOD{index}: {model.triangles:,} triángulos · {model.vertex_count:,} vértices · "
            f"{w:.2f} × {h:.2f} × {d:.2f} m{tex}\nForma: {shape}{opens} · piezas: {', '.join(p.name for p in model.parts)}")
