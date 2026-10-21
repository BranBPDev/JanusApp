import json
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSlider,
    QVBoxLayout, QWidget,
)

from app.gui.ai_chat import ChatPanel
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
        self.preview = None        # lo que devolvió PreviewWorker

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        # ---------- Chat con la IA (a la izquierda, junto a las pestañas) ----------
        self.chat = ChatPanel(self._current_dict)
        self.chat.setFixedWidth(430)
        self.chat.spec_changed.connect(self._on_ai_spec)
        self.chat.generate_requested.connect(self._generate)
        self.chat.new_requested.connect(self.new_project)
        root.addWidget(self.chat)

        # ---------- Visor 3D ----------
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

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(200, self.chat.ensure_model)   # la IA integrada se carga sola al abrir la pestaña

    def _current_dict(self) -> dict:
        try:
            return json.loads(self.spec_text) if self.spec_text else {}
        except Exception:
            return {}

    def _on_ai_spec(self, text):
        if self._busy():
            QTimer.singleShot(300, lambda: self._on_ai_spec(text))
            return
        self._reset_result()
        self._set_spec(text)

    # ---------- JSON y vista previa ----------
    def _busy(self) -> bool:
        return any(w is not None and w.isRunning() for w in (self.worker, self.preview_worker))

    def _set_project(self, name):
        self.project_name = name
        self.chat.set_editing(name)

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
        self.chat.set_progress(None)
        for b in self.lod_buttons:
            b.setEnabled(False)

    def _set_spec(self, text: str):
        """Guarda el JSON y dibuja su vista previa en segundo plano."""
        self.spec_text, self.preview = text, None
        self.chat.set_status("Dibujando la vista previa…")
        self.preview_worker = PreviewWorker(text)
        self.preview_worker.done.connect(self._on_preview)
        self.preview_worker.failed.connect(self._on_preview_failed)
        self.preview_worker.start()

    def _on_preview(self, data):
        self.preview = data
        w, h, d = data["size"]
        bones = f" · {data['bones']} huesos" if data["bones"] else ""
        self.chat.set_status("")
        self.chat.add_preview(self._preview_pixmap(data), f"{data['name']}: {w:.3f} × {h:.3f} × {d:.3f} m{bones}", "<br>".join(data["notes"]))

    def _on_preview_failed(self, message):
        self.chat.set_status("")
        self.chat.say_error(f"El JSON no se puede usar: {message}")

    def _preview_pixmap(self, data) -> QPixmap:
        """Las seis vistas (y los interiores si los hay) en una sola imagen para el chat."""
        cell, gap = 128, 6
        keys = [k for k, _ in VIEW_TITLES]
        inner = [k for k in ("movable", "fixed") if k in data["interiors"]]
        rows = 2 + (1 if inner else 0)
        pix = QPixmap(3 * cell + 2 * gap, rows * cell + (rows - 1) * gap)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        for i, key in enumerate(keys):
            if key in data["views"]:
                p.drawPixmap((i % 3) * (cell + gap), (i // 3) * (cell + gap), array_pixmap([data["views"][key]], cell))
        for i, key in enumerate(inner):
            p.drawPixmap(i * (cell + gap), 2 * (cell + gap), array_pixmap([data["interiors"][key]], cell))
        p.end()
        return pix

    # ---------- Proyectos ----------
    def load_project(self, name: str):
        """Carga el JSON de un proyecto guardado para editarlo (se vuelve a leer y a dibujar su vista previa)."""
        if self._busy():
            self.chat.set_status("Espera a que termine la generación en curso.")
            return
        text = load_project_source(name)
        self._reset_result()
        self._set_project(name)
        if text is None:
            self.spec_text = None
            self.chat.say_error("Este proyecto se hizo con imágenes y no tiene JSON. Pídele a la IA que lo cree de nuevo.")
            return
        self.chat.say_ai(f"Proyecto <b>{name}</b> cargado. Dime qué quieres cambiar.")
        self._set_spec(text)

    def new_project(self):
        if self._busy():
            return
        self.spec_text, self.preview = None, None
        self._reset_result()
        self._set_project(None)
        self.chat.reset()
        self.chat.say_ai("Objeto vaciado. ¿Qué quieres crear?")

    # ---------- Generación ----------
    def _generate(self):
        if not self.spec_text or self._busy():
            return
        self.chat.set_generate_enabled(False)
        self.warn.hide()
        self.chat.set_progress(0)
        name = self.project_name or (self.preview or {}).get("name") or "objeto"
        self.worker = ShapeWorker(name, self.spec_text, (self.preview or {}).get("blueprint"))
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_progress(self, fraction, message):
        self.chat.set_progress(fraction)
        self.chat.set_status(message)

    def _on_failed(self, message):
        self.chat.set_generate_enabled(True)
        self.chat.set_progress(None)
        self.chat.set_status("")
        self.chat.say_error(f"Error al generar: {message}")

    def _on_done(self, result, root):
        self.result, self.project_root = result, root
        self._set_project(self.worker.name)
        self.chat.set_generate_enabled(True)
        self.chat.set_progress(None)
        self.chat.set_status("")
        self.chat.say_ai(f"Modelo 3D generado en {result.info['seconds']} s. Míralo a la derecha.")
        self.open_btn.setEnabled(True)
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
