from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSlider,
    QVBoxLayout, QWidget,
)

from app.gui.viewer import MeshViewer
from app.gui.widgets import ViewPair
from app.managers.shape_manager import ShapeWorker
from app.shape.naming import IMAGE_FILTER, VIEWS, classify, classify_interior, object_name
from app.shape.project import load_project_inputs


class ShapePage(QWidget):
    saved = Signal()   # se ha guardado un proyecto (la lista de Inicio debe refrescarse)

    def __init__(self):
        super().__init__()
        self.worker = None
        self.result = None
        self.project_root = None
        self.project_name = None   # proyecto existente que se está editando (None = proyecto nuevo)
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

        # Textura interior (opcional): tapa (pieza móvil) y base (pieza fija). Solo se usa si el objeto se abre.
        self.interior = ViewPair("Interior (opcional)", ("Tapa", "Base"))
        self.interior.view.add_btn.setToolTip("Textura del interior de la tapa")
        self.interior.grid.add_btn.setToolTip("Textura del interior de la base")
        grid.addWidget(self.interior, 3, 0)

        controls = QVBoxLayout()
        controls.setSpacing(8)
        load = QPushButton("Cargar vistas y mallas...")
        load.setToolTip("Elige todas las imágenes a la vez. Se asignan por el nombre: pokeball_frente.png, "
                        "pokeball_frente_malla.png, pokeball_interior_tapa.png y pokeball_interior_base.png.")
        load.clicked.connect(self._load_files)
        controls.addWidget(load)
        self.gen_btn = QPushButton("Generar modelo 3D", objectName="Primary")
        self.gen_btn.setCursor(Qt.PointingHandCursor)
        self.gen_btn.clicked.connect(self._generate)
        controls.addWidget(self.gen_btn)
        self.editing = QLabel("", objectName="Muted")
        self.editing.setWordWrap(True)
        controls.addWidget(self.editing)
        self.new_btn = QPushButton("Nuevo proyecto")
        self.new_btn.setToolTip("Vacía las imágenes y empieza un proyecto nuevo.")
        self.new_btn.clicked.connect(self.new_project)
        self.new_btn.hide()
        controls.addWidget(self.new_btn)
        controls.addStretch()
        grid.addLayout(controls, 3, 1)
        lay.addLayout(grid)
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

    # ---------- Proyectos ----------
    def _set_inputs(self, views: dict, grids: dict, interiors: dict):
        for key, pair in self.pairs.items():
            pair.set_paths(views.get(key), grids.get(key))
        self.interior.set_paths(interiors.get("movable"), interiors.get("fixed"))

    def _set_project(self, name):
        self.project_name = name
        self.editing.setText(f"Editando: {name}" if name else "")
        self.new_btn.setVisible(bool(name))

    def _reset_result(self):
        self.result, self.project_root = None, None
        self.viewer.set_model(None)
        self.open_row.hide()
        self.open_slider.setValue(0)
        self.open_btn.setEnabled(False)
        self.info.clear()
        self.warn.hide()
        self.progress.setValue(0)
        for b in self.lod_buttons:
            b.setEnabled(False)

    def load_project(self, name: str):
        """Carga las vistas, mallas y texturas interiores de un proyecto guardado para editarlas y volver a generar."""
        if self.worker is not None and self.worker.isRunning():
            self.status.setText("Espera a que termine la generación en curso.")
            return
        inputs = load_project_inputs(name)
        self._set_inputs(inputs["views"], inputs["grids"], inputs["interiors"])
        self._reset_result()
        self._set_project(name)
        self.status.setText("Cambia las imágenes que quieras y pulsa «Generar modelo 3D» para actualizar el proyecto.")

    def new_project(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self._set_inputs({}, {}, {})
        self._reset_result()
        self._set_project(None)
        self.status.clear()

    # ---------- Acciones ----------
    def _load_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Seleccionar vistas y mallas", "", IMAGE_FILTER)
        unknown = []
        for p in paths:
            slots = classify_interior(p)
            if slots:
                for slot in slots:
                    (self.interior.view if slot == "movable" else self.interior.grid).set_path(p)
                continue
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
        interiors = {"movable": self.interior.view.path, "fixed": self.interior.grid.path}
        name = self.project_name or object_name([p for p in views.values() if p])
        self.worker = ShapeWorker(name, views, grids, interiors)
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
        self._set_project(self.worker.name)
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
        self.saved.emit()

    def _show_lod(self, index):
        model = self.result.lods[index]
        self.viewer.set_model(model)
        self.viewer.set_open(self.open_slider.value() / 100)
        w, h, d = model.size
        opens = " · se abre" if model.openable else ""
        if self.result.descriptor:
            kind = "Esfera" if self.result.descriptor["type"] == "sphere" else "Elipsoide"
            tex_in = self.result.descriptor.get("opening", {}) or {}
            tex_in = tex_in.get("interior_textures") or {}
            inside = " · textura interior" if any(tex_in.values()) else ""
            self.info.setText(
                f"{kind}: {model.triangles:,} triángulos · {model.vertex_count:,} vértices · "
                f"{w:.2f} × {h:.2f} × {d:.2f} m · textura {model.texture.shape[1]}×{model.texture.shape[0]}{opens}{inside}\n"
                f"Se exporta como .glb ya cortado · piezas: {', '.join(p.name for p in model.parts)}")
            return
        shape = "primitiva simple" if self.result.info.get("mode") == "primitiva" else "volumen de las vistas"
        tex = f" · textura {model.texture.shape[1]}×{model.texture.shape[0]}" if model.texture is not None else ""
        self.info.setText(
            f"LOD{index}: {model.triangles:,} triángulos · {model.vertex_count:,} vértices · "
            f"{w:.2f} × {h:.2f} × {d:.2f} m{tex}\nForma: {shape}{opens} · piezas: {', '.join(p.name for p in model.parts)}")
