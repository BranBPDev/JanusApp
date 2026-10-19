from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSlider,
    QVBoxLayout, QWidget,
)

from app.gui.viewer import MeshViewer
from app.managers.shape_manager import PreviewWorker, ShapeWorker
from app.shape.storage.project import load_project_source

PREVIEW_SIDE = 124
VIEW_TITLES = (("front", "Frente"), ("back", "Detrás"), ("left", "Izquierda"), ("right", "Derecha"), ("top", "Arriba"),
               ("bottom", "Abajo"))
JSON_FILTER = "Objeto JanusApp (*.json)"
BACKGROUND = (236, 237, 242)


def array_pixmap(layers, side: int) -> QPixmap:
    """Pixmap cuadrado con las capas RGBA (de abajo a arriba) compuestas sobre un fondo claro."""
    out = np.empty(layers[0].shape[:2] + (3,), np.float32)
    out[:] = BACKGROUND
    for layer in layers:
        a = layer[..., 3:4].astype(np.float32) / 255.0
        out = out * (1 - a) + layer[..., :3].astype(np.float32) * a
    data = np.ascontiguousarray(out.astype(np.uint8))
    image = QImage(data.data, data.shape[1], data.shape[0], data.shape[1] * 3, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(image).scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class ShapePage(QWidget):
    saved = Signal()   # se ha guardado un proyecto (la lista de Inicio debe refrescarse)

    def __init__(self):
        super().__init__()
        self.worker = None
        self.preview_worker = None
        self.result = None
        self.project_root = None
        self.project_name = None   # proyecto existente que se está editando (None = proyecto nuevo)
        self.spec_text = None      # el JSON del objeto
        self.spec_path = None
        self.preview = None        # lo que devolvió PreviewWorker
        self.thumbs = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(20)

        # ---------- Panel izquierdo ----------
        panel = QWidget()
        panel.setFixedWidth(410)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        title = QHBoxLayout()
        title.addWidget(QLabel("Generar objeto 3D", objectName="Title"))
        self.editing = QLabel("", objectName="Muted")
        title.addWidget(self.editing, 1, Qt.AlignBottom)
        lay.addLayout(title)
        lay.addWidget(QLabel("Un único archivo JSON describe el objeto: medidas, texturas, vistas, apertura y esqueleto.",
                             objectName="Subtitle", wordWrap=True))

        buttons = QHBoxLayout()
        self.load_btn = QPushButton("Cargar JSON...")
        self.load_btn.setToolTip("Elige el archivo .json del objeto.")
        self.load_btn.clicked.connect(self._load_json)
        buttons.addWidget(self.load_btn)
        self.reload_btn = QPushButton("Recargar")
        self.reload_btn.setToolTip("Vuelve a leer el archivo (si lo has editado).")
        self.reload_btn.setEnabled(False)
        self.reload_btn.clicked.connect(self._reload)
        buttons.addWidget(self.reload_btn)
        self.new_btn = QPushButton("Nuevo proyecto")
        self.new_btn.setToolTip("Vacía el objeto y empieza un proyecto nuevo.")
        self.new_btn.clicked.connect(self.new_project)
        self.new_btn.hide()
        buttons.addWidget(self.new_btn)
        lay.addLayout(buttons)
        self.summary = QLabel("Ningún objeto cargado.", objectName="Muted", wordWrap=True)
        lay.addWidget(self.summary)

        # Vista previa de las vistas descritas en el JSON
        card = QFrame(objectName="Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(10, 8, 10, 10)
        cl.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(QLabel("Vista previa", objectName="Brand"))
        head.addStretch()
        self.marks_box = QCheckBox("Cuadrícula y marcas")
        self.marks_box.setToolTip("Superpone la malla (cuadrícula a escala, corte, bisagra, botón, salientes y huesos).")
        self.marks_box.toggled.connect(self._refresh_preview)
        head.addWidget(self.marks_box)
        cl.addLayout(head)
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, (key, text) in enumerate(VIEW_TITLES):
            box = QVBoxLayout()
            box.setSpacing(1)
            thumb = QLabel(objectName="Thumb")
            thumb.setFixedSize(PREVIEW_SIDE, PREVIEW_SIDE)
            thumb.setAlignment(Qt.AlignCenter)
            self.thumbs[key] = thumb
            box.addWidget(thumb)
            box.addWidget(QLabel(text, objectName="CardTitle", alignment=Qt.AlignCenter))
            grid.addLayout(box, i // 3, i % 3)
        cl.addLayout(grid)
        inner = QHBoxLayout()
        inner.setSpacing(6)
        for key, text in (("movable", "Interior de la tapa"), ("fixed", "Interior de la base")):
            thumb = QLabel(objectName="Thumb")
            thumb.setFixedSize(56, 56)
            thumb.setAlignment(Qt.AlignCenter)
            self.thumbs[key] = thumb
            inner.addWidget(thumb)
            inner.addWidget(QLabel(text, objectName="CardTitle", wordWrap=True), 1)
        cl.addLayout(inner)
        lay.addWidget(card)

        self.gen_btn = QPushButton("Generar modelo 3D", objectName="Primary")
        self.gen_btn.setCursor(Qt.PointingHandCursor)
        self.gen_btn.setEnabled(False)
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

        self.rig_row = QWidget()        # esqueleto (solo si el objeto lo tiene)
        rrow = QHBoxLayout(self.rig_row)
        rrow.setContentsMargins(0, 0, 0, 0)
        rrow.addWidget(QLabel("Esqueleto"))
        self.animate_box = QCheckBox("Mover")
        self.animate_box.toggled.connect(self.viewer.set_animate)
        rrow.addWidget(self.animate_box)
        self.bones_box = QCheckBox("Ver huesos")
        self.bones_box.toggled.connect(self.viewer.set_bones)
        rrow.addWidget(self.bones_box)
        rrow.addStretch()
        self.rig_row.hide()
        right.addWidget(self.rig_row)

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

    # ---------- JSON y vista previa ----------
    def _busy(self) -> bool:
        return any(w is not None and w.isRunning() for w in (self.worker, self.preview_worker))

    def _set_project(self, name):
        self.project_name = name
        self.editing.setText(f"Editando: {name}" if name else "")
        self.new_btn.setVisible(bool(name))

    def _clear_preview(self):
        self.preview = None
        for thumb in self.thumbs.values():
            thumb.clear()
        self.gen_btn.setEnabled(False)

    def _reset_result(self):
        self.result, self.project_root = None, None
        self.viewer.set_model(None)
        self.open_row.hide()
        self.rig_row.hide()
        self.animate_box.setChecked(False)
        self.open_slider.setValue(0)
        self.open_btn.setEnabled(False)
        self.info.clear()
        self.warn.hide()
        self.progress.setValue(0)
        for b in self.lod_buttons:
            b.setEnabled(False)

    def _set_spec(self, text: str, path):
        """Guarda el JSON y dibuja su vista previa en segundo plano."""
        self.spec_text, self.spec_path = text, path
        self.reload_btn.setEnabled(bool(path))
        self._clear_preview()
        self.summary.setText("Dibujando la vista previa...")
        self.status.clear()
        self.preview_worker = PreviewWorker(text)
        self.preview_worker.done.connect(self._on_preview)
        self.preview_worker.failed.connect(self._on_preview_failed)
        self.preview_worker.start()

    def _load_json(self):
        if self._busy():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar el JSON del objeto", "", JSON_FILTER)
        if path:
            self._read(path)

    def _reload(self):
        if self.spec_path and not self._busy():
            self._read(self.spec_path)

    def _read(self, path):
        try:
            text = Path(path).read_text(encoding="utf-8")
        except Exception as e:
            self.status.setText(f"No se pudo leer el archivo: {e}")
            return
        self._reset_result()
        self._set_spec(text, path)

    def _on_preview(self, data):
        self.preview = data
        w, h, d = data["size"]
        bones = f" · {data['bones']} huesos" if data["bones"] else ""
        self.summary.setText(f"{data['name']}: {w:.3f} × {h:.3f} × {d:.3f} m (ancho × alto × fondo){bones}")
        self.status.setText("\n".join(data["notes"]) if data["notes"] else "Revisa la vista previa y pulsa «Generar modelo 3D».")
        self._refresh_preview()
        self.gen_btn.setEnabled(True)

    def _on_preview_failed(self, message):
        self.summary.setText("El JSON no se puede usar.")
        self.status.setText(message)
        self.gen_btn.setEnabled(False)

    def _refresh_preview(self, *_):
        data = self.preview
        if not data:
            return
        marks = self.marks_box.isChecked()
        for key, _title in VIEW_TITLES:
            thumb = self.thumbs[key]
            if key in data["views"]:
                layers = [data["views"][key]] + ([data["grids"][key]] if marks else [])
                thumb.setPixmap(array_pixmap(layers, PREVIEW_SIDE))
            else:
                thumb.clear()
        for key in ("movable", "fixed"):
            thumb = self.thumbs[key]
            if key in data["interiors"]:
                thumb.setPixmap(array_pixmap([data["interiors"][key]], 52))
            else:
                thumb.clear()

    # ---------- Proyectos ----------
    def load_project(self, name: str):
        """Carga el JSON de un proyecto guardado para editarlo (se vuelve a leer y a dibujar su vista previa)."""
        if self._busy():
            self.status.setText("Espera a que termine la generación en curso.")
            return
        text = load_project_source(name)
        self._reset_result()
        self._set_project(name)
        if text is None:
            self._clear_preview()
            self.spec_text = None
            self.summary.setText("Este proyecto se hizo con imágenes y no tiene JSON.")
            self.status.setText("Carga un JSON para volver a generarlo con el formato nuevo.")
            return
        self._set_spec(text, None)

    def new_project(self):
        if self._busy():
            return
        self.spec_text, self.spec_path = None, None
        self.reload_btn.setEnabled(False)
        self._clear_preview()
        self._reset_result()
        self._set_project(None)
        self.summary.setText("Ningún objeto cargado.")
        self.status.clear()

    # ---------- Generación ----------
    def _generate(self):
        if not self.spec_text or self._busy():
            return
        self.gen_btn.setEnabled(False)
        self.warn.hide()
        self.progress.setValue(0)
        name = self.project_name or (self.preview or {}).get("name") or "objeto"
        self.worker = ShapeWorker(name, self.spec_text, (self.preview or {}).get("blueprint"))
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
        self.rig_row.setVisible(result.lods[0].rigged)
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
        opens = (" · se abre" if model.openable else "") + (f" · esqueleto de {len(model.skeleton)} huesos" if model.rigged else "")
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
