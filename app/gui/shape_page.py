import unicodedata
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFontMetrics, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox, QButtonGroup, QCheckBox, QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QProgressBar, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget,
)

from app.gui.viewer import MeshViewer
from app.managers.shape_manager import ShapeWorker
from app.shape.pipeline import ShapeParams
from app.shape.project import sanitize_name

IMAGE_FILTER = "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp *.tga *.tif *.tiff)"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tga", ".tif", ".tiff"}

VIEWS = (
    ("front", "Frente", ("front", "frente", "delante", "frontal")),
    ("back", "Detrás", ("back", "atras", "detras", "trasera", "posterior", "rear")),
    ("top", "Arriba", ("top", "arriba", "superior", "cenital")),
    ("left", "Izquierda", ("left", "izq")),
    ("right", "Derecha", ("right", "der")),
)


def _normalize(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def guess_view(filename: str):
    name = _normalize(Path(filename).stem)
    for key, _, words in sorted(VIEWS, key=lambda v: v[0] not in ("left", "right")):  # izquierda/derecha primero
        if any(w in name for w in words):
            return key
    return None


class ViewSlot(QFrame):
    def __init__(self, key: str, title: str):
        super().__init__(objectName="Card")
        self.key, self.path = key, None
        self.setAcceptDrops(True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(10)

        self.thumb = QLabel(alignment=Qt.AlignCenter, objectName="Thumb")
        self.thumb.setFixedSize(56, 56)
        lay.addWidget(self.thumb)

        info = QVBoxLayout()
        info.setSpacing(0)
        info.addWidget(QLabel(title, objectName="Brand"))
        self.file_label = QLabel("Sin imagen", objectName="Muted")
        info.addWidget(self.file_label)
        lay.addLayout(info, 1)

        self.pick_btn = QPushButton("Elegir")
        self.pick_btn.clicked.connect(self._pick)
        self.clear_btn = QPushButton("Quitar")
        self.clear_btn.clicked.connect(lambda: self.set_path(None))
        lay.addWidget(self.pick_btn)
        lay.addWidget(self.clear_btn)
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
            self.thumb.clear()
            self.file_label.setText("Sin imagen")
        else:
            self.thumb.setPixmap(pix.scaled(52, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            name = QFontMetrics(self.file_label.font()).elidedText(Path(self.path).name, Qt.ElideMiddle, 140)
            self.file_label.setText(name)
        self.clear_btn.setEnabled(bool(self.path))

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if Path(p).suffix.lower() in IMAGE_SUFFIXES:
                self.set_path(p)
                break


def _row(text, widget, tip=""):
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    label = QLabel(text)
    label.setFixedWidth(80)
    label.setToolTip(tip)
    widget.setToolTip(tip)
    lay.addWidget(label)
    lay.addWidget(widget, 1)
    return box


def _meters(value, maximum=1000.0, special=None):
    box = QDoubleSpinBox()
    box.setRange(0.0 if special else 0.01, maximum)
    box.setDecimals(2)
    box.setValue(value)
    box.setSuffix(" m")
    box.setButtonSymbols(QAbstractSpinBox.NoButtons)
    if special:
        box.setSpecialValueText(special)
    return box


def _card(title: str):
    card = QFrame(objectName="Card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 12, 14, 14)
    lay.setSpacing(8)
    lay.addWidget(QLabel(title, objectName="Section"))
    return card, lay


class ShapePage(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.result = None
        self.project_root = None
        self.slots = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(20)

        # ---------- Panel izquierdo ----------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setFixedWidth(430)
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 14, 0)
        lay.setSpacing(12)
        lay.addWidget(QLabel("Generar objeto 3D", objectName="Title"))
        lay.addWidget(QLabel("Carga las vistas ortográficas del objeto.", objectName="Subtitle"))

        self.name_edit = QLineEdit("objeto")
        self.name_edit.setPlaceholderText("Nombre del objeto")
        lay.addWidget(_row("Nombre", self.name_edit))

        views_card, vlay = _card("VISTAS")
        for key, title, _ in VIEWS:
            slot = ViewSlot(key, title)
            self.slots[key] = slot
            vlay.addWidget(slot)
        load_multi = QPushButton("Cargar varias a la vez...")
        load_multi.setToolTip("Asigna cada imagen por su nombre (front, back, top, left, right / frente, atrás...).")
        load_multi.clicked.connect(self._load_multiple)
        vlay.addWidget(load_multi)
        lay.addWidget(views_card)

        size_card, slay = _card("TAMAÑO")
        self.height = _meters(1.0)
        self.length = _meters(0.0, special="Auto")
        slay.addWidget(_row("Alto", self.height, "Alto del objeto en metros."))
        slay.addWidget(_row("Largo", self.length, "Mayor dimensión horizontal en metros. Auto = proporcional al alto."))
        lay.addWidget(size_card)

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
        scroll.setWidget(panel)
        root.addWidget(scroll)

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
    def _load_multiple(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Seleccionar vistas", "", IMAGE_FILTER)
        unknown = []
        for p in paths:
            key = guess_view(p)
            if key:
                self.slots[key].set_path(p)
            else:
                unknown.append(Path(p).name)
        if unknown:
            self.status.setText("Sin asignar (nombre no reconocido): " + ", ".join(unknown))

    def _generate(self):
        paths = {k: s.path for k, s in self.slots.items()}
        if not paths["front"] or not (paths["left"] or paths["right"]):
            self.status.setText("Se necesitan al menos la vista frontal y una vista lateral.")
            return
        name = sanitize_name(self.name_edit.text()) or "objeto"
        params = ShapeParams(height=self.height.value(), length=self.length.value())
        self.gen_btn.setEnabled(False)
        self.warn.hide()
        self.progress.setValue(0)
        self.worker = ShapeWorker(name, paths, params)
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
            b.setEnabled(i < len(result.lods))
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
        kind = "primitiva simple" if self.result.info.get("mode") == "primitiva" else "volumen de las vistas"
        parts = ", ".join(p.name for p in model.parts)
        tex = f" · textura {model.texture.shape[1]}×{model.texture.shape[0]}" if model.texture is not None else ""
        self.info.setText(
            f"LOD{index}: {model.triangles:,} triángulos · {model.vertex_count:,} vértices · "
            f"{w:.2f} × {h:.2f} × {d:.2f} m{tex}\nObjeto {kind}{' · abrible' if model.openable else ''} · piezas: {parts}")
