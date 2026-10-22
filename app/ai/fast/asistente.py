"""IA rápida: petición (+ imágenes/JSON adjuntos) → programa de piezas (lo escribe el modelo) → JSON del objeto."""
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.ai.assistant import vision
from app.ai.fast import programa
from app.ai.fast.modelo import FastModel
from app.ai.fast.texto import prepare
from app.shape.spec.schema import FORMAT, SpecError

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}


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


def palette(path, k=4) -> list:
    """Colores dominantes de una imagen (sin el fondo blanco o transparente), del más al menos presente."""
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    im.thumbnail((72, 72))
    px = np.asarray(im, np.float32).reshape(-1, 4)
    px = px[(px[:, 3] > 200) & (px[:, :3].min(1) < 240)][:, :3]
    if len(px) < k:
        return []
    cent, lab = vision._kmeans(px, k)
    order = np.argsort(-np.bincount(lab, minlength=k))
    return [vision._hex(cent[i]) for i in order]


class Asistente:
    def __init__(self, model_path):
        self.model = FastModel(model_path)

    def pedir(self, text, spec, adjuntos=(), **_) -> Resultado:
        t0 = time.perf_counter()
        avisos, colors, base = [], [], spec
        for path in adjuntos:
            ext = Path(path).suffix.lower()
            if ext in IMAGE_EXT:
                colors = palette(path)
                if not colors:
                    avisos.append(f"No he sacado colores de {Path(path).name}.")
            elif ext == ".json":
                try:
                    data = json.loads(Path(path).read_text(encoding="utf-8"))
                    if isinstance(data, dict) and data.get("formato") == FORMAT:
                        base = data
                        avisos.append(f"Tomo {Path(path).name} como objeto de partida.")
                except Exception:
                    avisos.append(f"{Path(path).name} no es un JSON de objeto.")
            else:
                avisos.append(f"Ignoro {Path(path).name}: adjunta imágenes o un JSON de objeto.")
        words, hexes, nums = prepare(text, colors)
        ctx = programa.state(base) + (["img"] if colors else [])
        prog = self.model.generate(ctx, words)
        try:
            new, log = programa.run(base, prog, hexes, nums)
        except SpecError as e:
            raise SpecError(f"{e} (programa de la IA: {' '.join(prog)})")
        if self.model.confidence < 0.55:
            avisos.append("No estoy del todo seguro de haberte entendido; revisa el resultado o dímelo con otras palabras.")
        new.setdefault("formato", FORMAT)
        dt = time.perf_counter() - t0
        return Resultado(new, log, avisos=avisos, salida=" ".join(prog), segundos=dt)
