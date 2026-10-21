import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from app.managers.ai_manager import AskWorker, LoadWorker
from app.utils.paths_util import find_models

ATTACH_FILTER = "Imágenes y archivos (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.json *.txt *.md *.csv)"
MAX_UNDO = 30
SUGGESTIONS = (
    ("Esfera simple", "Hazme una esfera simple amarilla arriba y blanca abajo"),
    ("Esfera con banda y botón", "Hazme una esfera que se abre, con una banda negra en el centro y un botón"),
    ("Cambiar banda por cuerda", "Cambia la banda por una cuerda roja que rodee el botón"),
)


class _Input(QPlainTextEdit):
    submitted = Signal()

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not e.modifiers() & Qt.ShiftModifier:
            self.submitted.emit()
        else:
            super().keyPressEvent(e)


def _bubble(html: str, kind: str) -> QFrame:
    frame = QFrame(objectName="BubbleUser" if kind == "user" else "BubbleAi")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(12, 9, 12, 9)
    lay.setSpacing(6)
    label = QLabel(html, wordWrap=True, textInteractionFlags=Qt.TextSelectableByMouse)
    label.setTextFormat(Qt.RichText)
    lay.addWidget(label)
    return frame


class ChatPanel(QFrame):
    """Chat con la IA integrada: pides o cambias el objeto, ves su vista previa en la respuesta y generas el 3D desde ahí."""
    spec_changed = Signal(str)       # nuevo JSON completo del objeto
    generate_requested = Signal()
    new_requested = Signal()

    def __init__(self, current_spec):
        super().__init__(objectName="Card")
        self.current_spec = current_spec     # función: () -> dict del JSON actual o {}
        self.assistant = None
        self.load_worker = self.ask_worker = None
        self.undo, self.attachments = [], []
        self.pending = None
        self.gen_buttons = []
        self.model_state = "idle"            # idle | loading | ready | missing | failed
        self.stage = ""
        self.setAcceptDrops(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(QLabel("Asistente", objectName="Brand"))
        self.state = QLabel("", objectName="Muted")
        head.addWidget(self.state, 1)
        self.editing = QLabel("", objectName="Muted")
        head.addWidget(self.editing)
        self.new_btn = QPushButton("Nuevo")
        self.new_btn.setToolTip("Vacía el objeto y empieza uno nuevo.")
        self.new_btn.clicked.connect(self.new_requested.emit)
        head.addWidget(self.new_btn)
        lay.addLayout(head)

        self.scroll = QScrollArea(widgetResizable=True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        self.msgs = QVBoxLayout(holder)
        self.msgs.setContentsMargins(0, 0, 4, 0)
        self.msgs.setSpacing(8)
        self.msgs.addStretch()
        self.scroll.setWidget(holder)
        self.scroll.verticalScrollBar().rangeChanged.connect(lambda _a, b: self.scroll.verticalScrollBar().setValue(b))
        lay.addWidget(self.scroll, 1)

        self.chips = QWidget()
        chips = QVBoxLayout(self.chips)
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(4)
        for text, prompt in SUGGESTIONS:
            b = QPushButton(text, objectName="Chip")
            b.clicked.connect(lambda _=False, p=prompt: self._suggest(p))
            chips.addWidget(b)
        lay.addWidget(self.chips)

        self.progress = QProgressBar(textVisible=False)
        self.progress.setRange(0, 1000)
        self.progress.hide()
        lay.addWidget(self.progress)
        self.status = QLabel("", objectName="Muted", wordWrap=True)
        lay.addWidget(self.status)

        self.attached = QLabel("", objectName="Muted", wordWrap=True)
        self.attached.hide()
        lay.addWidget(self.attached)
        self.input = _Input()
        self.input.setFixedHeight(70)
        self.input.setPlaceholderText("Describe el objeto o lo que quieres cambiar…")
        self.input.submitted.connect(self._send)
        lay.addWidget(self.input)
        row = QHBoxLayout()
        self.attach_btn = QPushButton("Adjuntar")
        self.attach_btn.setToolTip("Imágenes de referencia y archivos de ejemplo. También puedes arrastrarlos al chat.")
        self.attach_btn.clicked.connect(self._attach)
        row.addWidget(self.attach_btn)
        self.review_box = QCheckBox("Revisar")
        self.review_box.setToolTip("La IA comprueba y corrige su resultado (más lento).")
        row.addWidget(self.review_box)
        row.addStretch()
        self.undo_btn = QPushButton("Deshacer")
        self.undo_btn.clicked.connect(self._undo)
        row.addWidget(self.undo_btn)
        self.stop_btn = QPushButton("Parar")
        self.stop_btn.clicked.connect(self._stop)
        row.addWidget(self.stop_btn)
        self.send_btn = QPushButton("Enviar", objectName="Primary")
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.send_btn)
        lay.addLayout(row)

        self.say_ai("Hola. Dime qué objeto quieres o qué cambiar del actual; puedes adjuntar imágenes de referencia.")
        self._sync()

    # ---------- mensajes ----------
    def _add(self, widget, align=None):
        self.msgs.insertWidget(self.msgs.count() - 1, widget)
        self.chips.setVisible(False)

    def say_user(self, html):
        self._add(_bubble(html, "user"))

    def say_ai(self, html):
        self._add(_bubble(html, "ai"))

    def say_error(self, text):
        self.say_ai(f"<span style='color:#F87171'>{text}</span>")

    def add_preview(self, pixmap, summary, notes="", can_generate=True):
        """Respuesta con la vista previa del objeto y los botones para generarlo o guardarlo."""
        frame = _bubble(f"<b>{summary}</b>" + (f"<br><span style='color:#FBBF24'>{notes}</span>" if notes else ""), "ai")
        lay = frame.layout()
        pic = QLabel(alignment=Qt.AlignCenter)
        pic.setPixmap(pixmap)
        lay.addWidget(pic)
        row = QHBoxLayout()
        gen = QPushButton("Generar modelo 3D", objectName="Primary")
        gen.setEnabled(can_generate)
        gen.clicked.connect(self.generate_requested.emit)
        row.addWidget(gen, 1)
        save = QPushButton("Guardar JSON")
        save.clicked.connect(self._save)
        row.addWidget(save)
        lay.addLayout(row)
        for b in self.gen_buttons:
            b.setEnabled(False)
            b.setToolTip("Hay una versión más reciente.")
        self.gen_buttons.append(gen)
        self._add(frame)

    def set_generate_enabled(self, enabled: bool):
        if self.gen_buttons:
            self.gen_buttons[-1].setEnabled(enabled)

    def set_status(self, text):
        self.status.setText(text)

    def set_progress(self, fraction):
        self.progress.setVisible(fraction is not None)
        if fraction is not None:
            self.progress.setValue(int(fraction * 1000))

    def set_editing(self, name):
        self.editing.setText(f"· {name}" if name else "")

    # ---------- estado ----------
    def busy(self):
        return any(w is not None and w.isRunning() for w in (self.load_worker, self.ask_worker))

    def _asking(self):
        return self.ask_worker is not None and self.ask_worker.isRunning()

    def _sync(self):
        asking = self._asking()
        self.send_btn.setEnabled(not asking and self.model_state in ("ready", "loading"))
        self.stop_btn.setEnabled(asking)
        self.undo_btn.setEnabled(bool(self.undo) and not asking)
        self.attach_btn.setEnabled(not asking)
        self.input.setEnabled(not asking)
        self.attached.setVisible(bool(self.attachments))
        self.attached.setText("Adjuntos: " + ", ".join(Path(a).name for a in self.attachments))
        self.state.setText({"idle": "", "loading": "· cargando la IA…", "ready": "· IA lista", "missing": "· sin modelo", "failed": "· error"}[self.model_state])

    # ---------- modelo (integrado: se carga solo) ----------
    def ensure_model(self):
        if self.model_state != "idle":
            return
        files = find_models()
        if not files:
            self.model_state = "missing"
            self.say_error("No se encuentra el modelo de IA (un archivo <b>.gguf</b> en <i>app/models/ia</i> junto a la aplicación). "
                           "Debería venir incluido en la descarga; reinstala o actualiza la aplicación.")
            self._sync()
            return
        self.model_state = "loading"
        self.model_name = files[0].name
        self.set_progress(0)
        self.set_status("Cargando la IA en la memoria (solo la primera vez al abrir la app)…")
        self.load_worker = LoadWorker(str(files[0]))
        self.load_worker.progress.connect(self.set_progress)
        self.load_worker.loaded.connect(self._on_loaded)
        self.load_worker.failed.connect(self._on_load_failed)
        self.load_worker.start()
        self._sync()

    def _on_loaded(self, assistant):
        self.assistant, self.model_state = assistant, "ready"
        self.set_progress(None)
        self.set_status("")
        self._sync()
        if self.pending:
            text, self.pending = self.pending, None
            self._ask(text)

    def _on_load_failed(self, message):
        self.model_state = "failed"
        self.set_progress(None)
        self.set_status("")
        self.say_error(message)
        self._sync()

    # ---------- adjuntos ----------
    def _attach(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Adjuntar imágenes o archivos", "", ATTACH_FILTER)
        self._add_files(paths)

    def _add_files(self, paths):
        self.attachments += [p for p in paths if p not in self.attachments]
        self._sync()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self._add_files([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    # ---------- conversación ----------
    def _suggest(self, prompt):
        self.input.setPlainText(prompt)
        self._send()

    def _send(self):
        text = self.input.toPlainText().strip()
        if not text or self._asking():
            return
        if self.model_state not in ("ready", "loading"):
            return
        self.input.clear()
        files = list(self.attachments)
        self.attachments = []
        self.say_user(text.replace("\n", "<br>") + (f"<br><small>Adjuntos: {', '.join(Path(a).name for a in files)}</small>" if files else ""))
        self._files = files
        if self.model_state == "loading":
            self.pending = text
            self.set_status("Cargando la IA… tu petición se enviará en cuanto esté lista.")
            self._sync()
            return
        self._ask(text)

    def _ask(self, text):
        self.set_status("Preparando la petición…")
        self.stage = ""
        self.ask_worker = AskWorker(self.assistant, text, self.current_spec(), getattr(self, "_files", []), self.review_box.isChecked())
        self._files = []
        self.ask_worker.stage.connect(lambda s: setattr(self, "stage", s))
        self.ask_worker.tokens.connect(lambda n: self.set_status(f"{self.stage} {n} fichas"))
        self.ask_worker.done.connect(self._on_done)
        self.ask_worker.failed.connect(self._on_failed)
        self.ask_worker.cancelled.connect(lambda: (self.set_status(""), self.say_ai("<i>Cancelado.</i>")))
        self.ask_worker.finished.connect(self._sync)
        self.ask_worker.start()
        self._sync()

    def _stop(self):
        if self.ask_worker is not None:
            self.ask_worker.stop()

    def _on_failed(self, message):
        self.set_status("")
        self.say_error(message)

    def _on_done(self, r):
        self.set_status("")
        previous = self.current_spec()
        if previous:
            self.undo.append(previous)
            del self.undo[:-MAX_UNDO]
        changes = "".join(f"<li>{c}</li>" for c in r.cambios)
        notes = "".join(f"<li><span style='color:#FBBF24'>{a}</span></li>" for a in r.avisos)
        retry = f" (a la {r.intentos}ª tras corregirme)" if r.intentos > 1 else ""
        review = f" Revisión: {r.revisado}." if r.revisado else ""
        self.say_ai(f"Hecho{retry}.{review}<ul style='margin:4px 0 0 0'>{changes}</ul>" + (f"No cumplido del todo:<ul>{notes}</ul>" if notes else ""))
        self.spec_changed.emit(json.dumps(r.spec, ensure_ascii=False, indent=1))

    def _undo(self):
        if self.undo and not self._asking():
            self.spec_changed.emit(json.dumps(self.undo.pop(), ensure_ascii=False, indent=1))
            self.say_ai("<i>Cambio deshecho.</i>")
            self._sync()

    def _save(self):
        spec = self.current_spec()
        if not spec:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar el JSON", f"{spec.get('nombre', 'objeto')}.json", "Objeto JanusApp (*.json)")
        if path:
            Path(path).write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
            self.set_status(f"Guardado en {path}")

    def reset(self):
        """Nuevo objeto: se olvida el historial de cambios."""
        self.undo = []
        self._sync()

    def refresh(self):
        self._sync()
