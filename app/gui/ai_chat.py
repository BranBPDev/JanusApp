import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFileDialog, QInputDialog, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from app.ai.fast import registro
from app.ai.fast.asistente import Asistente
from app.shape.spec.schema import SpecError
from app.utils.logger_util import get_logger
from app.utils.paths_util import FAST_MODEL

log = get_logger("AI_CHAT")

ATTACH_FILTER = "Imágenes y objetos (*.png *.jpg *.jpeg *.jfif *.bmp *.webp *.gif *.tif *.tiff *.tga *.svg *.json)"
MAX_UNDO = 30
SUGGESTIONS = (
    ("Esfera simple azul", "Hazme una esfera simple azul"),
    ("Esfera con banda y botón", "Hazme una esfera con banda y botón, arriba roja y abajo blanca, con la banda negra"),
    ("Banda → cuerda y triskel", "Cambia la banda por una cuerda roja y añade un triskel arriba"),
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
        self.undo, self.attachments, self.undo_ids = [], [], []
        self.last_id = None
        self.gen_buttons = []
        self.model_state = "idle"            # idle | loading | ready | missing | failed
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
        self.input.setAcceptDrops(False)      # los archivos soltados los recibe el chat como adjuntos
        self.input.setPlaceholderText("Describe el objeto o lo que quieres cambiar…")
        self.input.submitted.connect(self._send)
        lay.addWidget(self.input)
        row = QHBoxLayout()
        self.attach_btn = QPushButton("Adjuntar")
        self.attach_btn.setToolTip("Imágenes de referencia y archivos de ejemplo. También puedes arrastrarlos al chat.")
        self.attach_btn.clicked.connect(self._attach)
        row.addWidget(self.attach_btn)
        row.addStretch()
        self.undo_btn = QPushButton("Deshacer")
        self.undo_btn.clicked.connect(self._undo)
        row.addWidget(self.undo_btn)
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
        frame = _bubble(html, "ai")
        self._add(frame)
        return frame

    def _rating_row(self, frame, id_):
        """Botones para valorar la respuesta: alimentan el registro con el que se reentrena la IA."""
        row = QHBoxLayout()
        row.addStretch()
        label = QLabel("¿Lo hizo bien?", objectName="Muted")
        good, bad = QPushButton("Bien"), QPushButton("Mal")
        for b in (good, bad):
            b.setFixedWidth(60)
        row.addWidget(label)
        row.addWidget(good)
        row.addWidget(bad)
        frame.layout().addLayout(row)

        def done(text):
            for w in (good, bad):
                w.hide()
            label.setText(text)

        def on_good():
            registro.valoracion(id_, True)
            done("Anotado: bien.")

        def on_bad():
            text, ok = QInputDialog.getMultiLineText(self, "¿Qué debía hacer?", "Cuéntame con tus palabras qué esperabas (opcional):")
            registro.valoracion(id_, False, text.strip() if ok else "")
            done("Anotado: mal.")

        good.clicked.connect(on_good)
        bad.clicked.connect(on_bad)

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
    def _sync(self):
        self.undo_btn.setEnabled(bool(self.undo))
        self.attached.setVisible(bool(self.attachments))
        self.attached.setText("Adjuntos: " + ", ".join(Path(a).name for a in self.attachments))
        self.state.setText({"idle": "", "ready": "· IA lista", "missing": "· sin modelo", "failed": "· error"}[self.model_state])

    # ---------- modelo (integrado en la app: pesa unos KB y carga al instante) ----------
    def ensure_model(self):
        if self.model_state != "idle":
            return
        try:
            self.assistant = Asistente(str(FAST_MODEL))
            self.model_state = "ready"
        except Exception as e:
            log.error(f"No se pudo cargar la IA: {e}", exc_info=True)
            self.model_state = "failed"
            self.say_error(f"No se pudo cargar la IA integrada ({FAST_MODEL.name}): {e}")
        self._sync()

    # ---------- adjuntos ----------
    def _attach(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Adjuntar imágenes o un JSON de objeto", "", ATTACH_FILTER)
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
        if not text:
            return
        self.ensure_model()
        self.input.clear()
        files, self.attachments = list(self.attachments), []
        self.say_user(text.replace("\n", "<br>") + (f"<br><small>Adjuntos: {', '.join(Path(a).name for a in files)}</small>" if files else ""))
        self._sync()
        if self.assistant is None:
            return
        previous = self.current_spec()
        try:
            r = self.assistant.pedir(text, previous, files)
        except SpecError as e:
            self.say_error(str(e))
            return
        except Exception as e:
            log.error(f"Error de la IA: {e}", exc_info=True)
            self.say_error(f"Error de la IA: {e}")
            return
        if previous:
            self.undo.append(previous)
            del self.undo[:-MAX_UNDO]
        changes = "".join(f"<li>{c}</li>" for c in r.cambios)
        notes = "".join(f"<li><span style='color:#FBBF24'>{a}</span></li>" for a in r.avisos)
        frame = self.say_ai(f"Hecho en {r.segundos * 1000:.0f} ms.<ul style='margin:4px 0 0 0'>{changes}</ul>" + (f"<ul>{notes}</ul>" if notes else ""))
        self._rating_row(frame, r.id)
        self.last_id = r.id
        self.undo_ids.append(r.id)
        self.spec_changed.emit(json.dumps(r.spec, ensure_ascii=False, indent=1))

    def _undo(self):
        if self.undo:
            if self.undo_ids:
                registro.deshacer(self.undo_ids.pop())
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
        """Chat nuevo: se borran los mensajes y el historial de cambios."""
        while self.msgs.count() > 1:
            item = self.msgs.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.gen_buttons, self.undo, self.attachments, self.undo_ids = [], [], [], []
        self.input.clear()
        self.set_status("")
        self.set_progress(None)
        self.chips.setVisible(True)
        self.say_ai("Chat nuevo. ¿Qué objeto quieres crear?")
        self.chips.setVisible(True)
        self._sync()

    def refresh(self):
        self._sync()
