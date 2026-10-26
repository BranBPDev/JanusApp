"""IA rápida: petición (+ imágenes/JSON adjuntos) → programa de piezas (lo escribe el modelo) → JSON del objeto."""
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.ai.assistant import vision
from app.ai.fast import catalogo, imagen3d, programa, registro
from app.ai.fast.colores import bases_in
from app.ai.fast.modelo import FastModel
from app.ai.fast.texto import prepare
from app.shape.spec.schema import FORMAT, SpecError

IMAGE_EXT = imagen3d.IMAGE_EXT | imagen3d.VECTOR_EXT | imagen3d.malla3d.MODEL_EXT


@dataclass
class Resultado:
    spec: dict
    cambios: list
    informe: str = ""
    avisos: list = field(default_factory=list)
    intentos: int = 1
    revisado: str = ""
    salida: str = ""
    segundos: float = 0.0
    id: str = ""


def _background(rgb, alpha):
    """Máscara del fondo: transparente, o píxeles claros conectados con el borde de la imagen."""
    h, w = alpha.shape
    light = (rgb.min(-1) > 235) | (alpha < 40)
    bg = np.zeros((h, w), bool)
    bg[0, :] = bg[-1, :] = bg[:, 0] = bg[:, -1] = True
    bg &= light
    for _ in range(h + w):                      # propagación desde el borde
        grow = bg.copy()
        grow[1:] |= bg[:-1]
        grow[:-1] |= bg[1:]
        grow[:, 1:] |= bg[:, :-1]
        grow[:, :-1] |= bg[:, 1:]
        grow &= light
        if (grow == bg).all():
            break
        bg = grow
    return bg


def palette(path, k=6) -> list:
    """Colores de una imagen en el orden de las piezas de una esfera con banda: [tapa, fondo, banda, botón].
    tapa = el color más vivo; fondo = el más claro; banda = el más oscuro; botón = el segundo más claro (o el fondo)."""
    im = imagen3d.open_image(path).convert("RGBA")
    im.thumbnail((84, 84))
    arr = np.asarray(im, np.float32)
    bg = _background(arr[..., :3], arr[..., 3])
    px = arr[..., :3][~bg & (arr[..., 3] > 200)]
    if len(px) < 40:
        return []
    cent, lab = vision._kmeans(px, k)
    share = np.bincount(lab, minlength=k) / len(px)
    keep = [i for i in range(k) if share[i] > 0.02]
    chroma = cent.max(1) - cent.min(1)
    light = cent.mean(1)
    tapa = max(keep, key=lambda i: chroma[i] * (0.5 + share[i]))
    rest = [i for i in keep if i != tapa]
    dark = min(rest, key=lambda i: light[i]) if rest else tapa
    rest2 = [i for i in rest if i != dark]
    fondo = max(rest2, key=lambda i: light[i] - 0.3 * chroma[i]) if rest2 else tapa
    rest3 = [i for i in rest2 if i != fondo]
    boton = max(rest3, key=lambda i: light[i] - 0.3 * chroma[i]) if rest3 else fondo
    return [vision._hex(cent[i]) for i in (tapa, fondo, dark, boton)]


def _wide(path) -> bool:
    try:
        w, h = imagen3d.open_image(path).size
        return w / h >= imagen3d.SHEET_MIN_ASPECT
    except Exception:
        return False


class Asistente:
    def __init__(self, model_path):
        self.model = FastModel(model_path)

    @staticmethod
    def _reference(words):
        """Nombre de la referencia registrada que se nombra en el texto (o None)."""
        try:
            refs = catalogo.referencias()
        except Exception:
            return None
        text = " " + " ".join(words) + " "
        for name, (aliases, *_rest) in refs.items():
            if any(f" {n} " in text for n in [name] + aliases):
                return name
        return None

    def pedir(self, text, spec, adjuntos=(), **_) -> Resultado:
        t0 = time.perf_counter()
        avisos, colors, base, images = [], [], spec, []
        for path in adjuntos:
            ext = Path(path).suffix.lower()
            if ext in IMAGE_EXT:
                images.append(path)
            elif ext == ".json":
                try:
                    data = json.loads(Path(path).read_text(encoding="utf-8"))
                    if isinstance(data, dict) and data.get("formato") == FORMAT:
                        base = data
                        avisos.append(f"Tomo {Path(path).name} como objeto de partida.")
                    else:
                        avisos.append(f"{Path(path).name} no es un objeto de JanusApp (falta «formato»: «{FORMAT}»).")
                except Exception:
                    avisos.append(f"{Path(path).name} no es un JSON válido.")
            else:
                avisos.append(f"No sé leer {Path(path).name}: adjunta imágenes (PNG, JPG, SVG…) o un JSON de objeto.")
        models = [p for p in images if Path(p).suffix.lower() in imagen3d.malla3d.MODEL_EXT]
        pics = [p for p in images if p not in models]
        views = {imagen3d.view_of(p) for p in pics}
        if pics:                                     # colores de la imagen de frente (o de la primera)
            ref = next((p for p in pics if imagen3d.view_of(p) == "frente"), pics[0])
            try:
                colors = palette(ref)
            except Exception:
                colors = []
            if not colors:
                avisos.append(f"No he sacado colores de {Path(ref).name}.")
        words, hexes, nums = prepare(text, colors)
        ctx = programa.state(base)
        if images:
            ctx += ["img"] + (["img_frente"] if "frente" in views else []) + (["img_lateral"] if views & {"lateral", "izquierda", "derecha"} else [])
            if any(not imagen3d.view_of(p) and _wide(p) for p in pics):
                ctx.append("img_hoja")                  # una sola imagen apaisada sin nombre de vista: suele ser una hoja con varias vistas
            if models:
                ctx.append("img_modelo")
        known = self._reference(words)
        if known:
            ctx.append("ref")                           # el texto nombra un objeto registrado en el catálogo (tabla referencias)
        prog = self.model.generate(ctx, words)
        vocab = self.model.vocab
        said = bases_in(w if w.startswith("<") else vocab.itos[vocab.word(w)] for w in words)
        names = [Path(a).name for a in adjuntos]
        lit = {"hex": hexes, "medidas_m": [round(n, 4) for n in nums]}
        try:
            new, log = programa.run(base, prog, hexes, nums, {"imagenes": images, "referencia": known}, said)
        except Exception as e:     # SpecError o cualquier fallo al montar las piezas: se registra para poder corregir a la IA
            registro.peticion(text, ctx, prog, False, f"{type(e).__name__}: {e}", self.model.confidence, adjuntos=names,
                              ms=(time.perf_counter() - t0) * 1000, literales=lit)
            raise SpecError(f"{e if isinstance(e, SpecError) else 'No he podido aplicarlo a este objeto.'} (programa de la IA: {' '.join(prog)})")
        if self.model.confidence < 0.55:
            avisos.append("No estoy del todo seguro de haberte entendido; revisa el resultado o dímelo con otras palabras.")
        new.setdefault("formato", FORMAT)
        dt = time.perf_counter() - t0
        id_ = registro.peticion(text, ctx, prog, True, "", self.model.confidence, log, avisos, names, dt * 1000, lit)
        return Resultado(new, log, avisos=avisos, salida=" ".join(prog), segundos=dt, id=id_)
