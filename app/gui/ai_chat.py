import json
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from app.managers.ai_manager import AskWorker, LoadWorker
from app.utils.paths_util import AI_MODELS_DIR

ATTACH_FILTER = "Imágenes y archivos (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.json *.txt *.md *.csv)"

MAX_UNDO = 30


class _Input(QPlainTextEdit):
    submitted = Signal()

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not e.modifiers() & Qt.ShiftModifier:
            self.submitted.emit()
        else:
            super().keyPressEvent(e)


class AiChatPanel(QWidget):
    """Chat con la IA local: pide un objeto o un cambio y el JSON se actualiza (y la vista previa con él)."""
    spec_changed = Signal(str)       # nuevo JSON completo del objeto

    def __init__(self, current_spec):
        super().__init__()
        self.current_spec = current_spec     # función: () -> dict del JSON actual o {}
        self.assistant = None
        self.load_worker = self.ask_worker = None
        self.undo = []
        self.attachments = []
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(QLabel("Asistente IA", objectName="Title"))
        lay.addWidget(QLabel("Corre dentro de la app, sin internet. Escribe el JSON completo de lo que pidas; puedes adjuntar imágenes y archivos de ejemplo.",
                             objectName="Subtitle", wordWrap=True))
        row = QHBoxLayout()
        self.models = QComboBox()
        self.models.setToolTip("Modelos .gguf de la carpeta app/models/ia")
        row.addWidget(self.models, 1)
        self.load_btn = QPushButton("Cargar")
        self.load_btn.clicked.connect(self._load)
        row.addWidget(self.load_btn)
        folder = QPushButton("Carpeta")
        folder.setToolTip("Abre la carpeta donde se coloca el archivo .gguf del modelo.")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(AI_MODELS_DIR))))
        row.addWidget(folder)
        lay.addLayout(row)
        self.progress = QProgressBar(textVisible=False)
        self.progress.setRange(0, 1000)
        self.progress.hide()
        lay.addWidget(self.progress)
        self.log = QTextBrowser()
        self.log.setOpenLinks(False)
        lay.addWidget(self.log, 1)
        self.status = QLabel("", objectName="Muted", wordWrap=True)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        self.attach_btn = QPushButton("Adjuntar...")
        self.attach_btn.setToolTip("Imágenes de referencia y archivos de ejemplo (JSON, texto). También puedes arrastrarlos aquí.")
        self.attach_btn.clicked.connect(self._attach)
        row.addWidget(self.attach_btn)
        self.attached = QLabel("", objectName="Muted", wordWrap=True)
        row.addWidget(self.attached, 1)
        self.clear_btn = QPushButton("Quitar")
        self.clear_btn.clicked.connect(self._clear_attachments)
        row.addWidget(self.clear_btn)
        lay.addLayout(row)
        self.review_box = QCheckBox("Revisar el resultado (la IA lo comprueba y lo corrige)")
        self.review_box.setChecked(True)
        lay.addWidget(self.review_box)
        self.input = _Input()
        self.input.setFixedHeight(64)
        self.input.setPlaceholderText("Ej.: una esfera simple azul · cambia la banda por una cuerda · haz que se vea como la imagen adjunta")
        self.input.submitted.connect(self._send)
        lay.addWidget(self.input)
        row = QHBoxLayout()
        self.send_btn = QPushButton("Enviar", objectName="Primary")
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.send_btn, 1)
        self.stop_btn = QPushButton("Parar")
        self.stop_btn.clicked.connect(self._stop)
        row.addWidget(self.stop_btn)
        self.undo_btn = QPushButton("Deshacer")
        self.undo_btn.clicked.connect(self._undo)
        row.addWidget(self.undo_btn)
        self.save_btn = QPushButton("Guardar JSON...")
        self.save_btn.clicked.connect(self._save)
        row.addWidget(self.save_btn)
        lay.addLayout(row)
        self._refresh_models()
        self._sync()

    # ---------- estado ----------
    def _refresh_models(self):
        self.models.clear()
        files = sorted(AI_MODELS_DIR.glob("*.gguf"))
        for f in files:
            self.models.addItem(f.name, str(f))
        if not files:
            self.say(f"No hay ningún modelo. Copia un archivo <b>.gguf</b> (Qwen2.5 Instruct, por ejemplo 0.5B o 1.5B en Q8_0 o Q4_K_M) "
                     f"en <i>{AI_MODELS_DIR}</i> y reabre esta página.")

    def _sync(self):
        loading = self.load_worker is not None and self.load_worker.isRunning()
        asking = self.ask_worker is not None and self.ask_worker.isRunning()
        self.load_btn.setEnabled(self.models.count() > 0 and not loading and not asking)
        self.load_btn.setText("Recargar" if self.assistant else "Cargar")
        self.send_btn.setEnabled(self.assistant is not None and not asking)
        self.stop_btn.setEnabled(asking)
        self.undo_btn.setEnabled(bool(self.undo) and not asking)
        self.save_btn.setEnabled(bool(self.current_spec()))
        self.input.setEnabled(self.assistant is not None and not asking)
        self.attach_btn.setEnabled(not asking)
        self.clear_btn.setEnabled(bool(self.attachments) and not asking)
        self.attached.setText(", ".join(Path(a).name for a in self.attachments))

    def say(self, html):
        self.log.append(html + "<br>")

    def busy(self):
        return any(w is not None and w.isRunning() for w in (self.load_worker, self.ask_worker))

    # ---------- modelo ----------
    def _load(self):
        path = self.models.currentData()
        if not path:
            return
        self.assistant = None
        self.progress.setValue(0)
        self.progress.show()
        self.status.setText("Cargando el modelo en la RAM (la primera vez tarda unos segundos)...")
        self.load_worker = LoadWorker(path)
        self.load_worker.progress.connect(lambda f: self.progress.setValue(int(f * 1000)))
        self.load_worker.loaded.connect(self._on_loaded)
        self.load_worker.failed.connect(self._on_load_failed)
        self.load_worker.finished.connect(self._sync)
        self.load_worker.start()
        self._sync()

    def _on_loaded(self, assistant):
        self.assistant = assistant
        self.progress.hide()
        self.status.setText("Modelo listo.")
        self.say(f"Modelo cargado: <b>{self.models.currentText()}</b>. Dime qué objeto quieres o qué cambiar.")

    def _on_load_failed(self, message):
        self.progress.hide()
        self.status.clear()
        self.say(f"<span style='color:#c0392b'>{message}</span>")

    # ---------- adjuntos ----------
    def _attach(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Adjuntar imágenes o archivos", "", ATTACH_FILTER)
        self._add(paths)

    def _add(self, paths):
        self.attachments += [p for p in paths if p not in self.attachments]
        self._sync()

    def _clear_attachments(self):
        self.attachments = []
        self._sync()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self._add([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    # ---------- conversación ----------
    def _send(self):
        text = self.input.toPlainText().strip()
        if not text or self.assistant is None or self.busy():
            return
        self.input.clear()
        files = list(self.attachments)
        self.say(f"<b>Tú:</b> {text}" + (f"<br><small>Adjuntos: {', '.join(Path(a).name for a in files)}</small>" if files else ""))
        self.status.setText("Leyendo lo adjunto y preparando la petición (puede tardar la primera vez)...")
        self.ask_worker = AskWorker(self.assistant, text, self.current_spec(), files, self.review_box.isChecked())
        self.attachments = []
        self.stage = ""
        self.ask_worker.stage.connect(lambda s: setattr(self, "stage", s))
        self.ask_worker.tokens.connect(lambda n: self.status.setText(f"{self.stage} {n} fichas"))
        self.ask_worker.done.connect(self._on_done)
        self.ask_worker.failed.connect(self._on_failed)
        self.ask_worker.cancelled.connect(lambda: (self.status.clear(), self.say("<i>Cancelado.</i>")))
        self.ask_worker.finished.connect(self._sync)
        self.ask_worker.start()
        self._sync()

    def _stop(self):
        if self.ask_worker is not None:
            self.ask_worker.stop()

    def _on_failed(self, message):
        self.status.clear()
        self.say(f"<b>IA:</b> <span style='color:#c0392b'>{message}</span>")

    def _on_done(self, r):
        self.status.clear()
        previous = self.current_spec()
        if previous:
            self.undo.append(previous)
            del self.undo[:-MAX_UNDO]
        changes = "".join(f"<li>{c}</li>" for c in r.cambios)
        notes = "".join(f"<li><span style='color:#b9770e'>{a}</span></li>" for a in r.avisos)
        warn = "".join(f"<li>{line[7:]}</li>" for line in r.informe.splitlines() if line.startswith("AVISO: "))
        retry = f" (a la {r.intentos}ª tras corregirme)" if r.intentos > 1 else ""
        review = f" Revisión: {r.revisado}." if r.revisado else ""
        self.say(f"<b>IA:</b> Hecho{retry}. JSON completo actualizado.{review}<ul>{changes}</ul>"
                 + (f"No cumplido del todo:<ul>{notes}</ul>" if notes else "")
                 + (f"Avisos del objeto:<ul>{warn}</ul>" if warn else "")
                 + "<small>" + r.informe.split("Silueta de frente:")[0].replace("\n", "<br>") + "</small>")
        self.spec_changed.emit(json.dumps(r.spec, ensure_ascii=False, indent=1))

    def _undo(self):
        if self.undo and not self.busy():
            self.spec_changed.emit(json.dumps(self.undo.pop(), ensure_ascii=False, indent=1))
            self.say("<i>Cambio deshecho.</i>")
            self._sync()

    def _save(self):
        spec = self.current_spec()
        if not spec:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar el JSON", f"{spec.get('nombre', 'objeto')}.json", "Objeto JanusApp (*.json)")
        if path:
            Path(path).write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
            self.say(f"<i>Guardado en {path}</i>")

    def refresh(self):
        self._sync()
