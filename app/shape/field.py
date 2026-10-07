import itertools
import numpy as np
from PIL import Image

# Ejes del mundo: X derecha (visto desde el frente), Y arriba, Z hacia la cámara frontal.
# Convención por defecto de las vistas (se corrige sola si 'auto_orient' está activo):
#   frente: cámara en +Z | detrás: cámara en -Z
#   derecha: el frente del objeto mira hacia la derecha de la imagen
#   izquierda: el frente mira hacia la izquierda de la imagen
#   arriba: el frente del objeto está en la parte inferior de la imagen


def compute_dims(masks: dict):
    """Proporciones (ancho, alto=1, fondo) a partir de las vistas."""
    def ratio(keys):
        vals = [masks[k].shape[1] / masks[k].shape[0] for k in keys if k in masks]
        return sum(vals) / len(vals) if vals else None

    w = ratio(("front", "back"))
    d = ratio(("left", "right"))
    return w, 1.0, d


def grid_shape(dims, resolution: int):
    cell = max(dims) / resolution
    return tuple(max(4, round(x / cell)) for x in dims), cell


def _resample(mask: np.ndarray, w: int, h: int) -> np.ndarray:
    img = Image.fromarray(mask.astype(np.uint8) * 255, "L")
    mh, mw = mask.shape
    method = Image.BOX if (mw >= w and mh >= h) else Image.BILINEAR
    return np.asarray(img.resize((w, h), method), dtype=np.float32) / 255.0


def make_arrays(masks: dict, shape):
    """Silueta de cada vista remuestreada a la rejilla (filas de arriba a abajo, como la imagen)."""
    nx, ny, nz = shape
    size = {"front": (nx, ny), "back": (nx, ny), "left": (nz, ny), "right": (nz, ny), "top": (nx, nz)}
    return {k: _resample(m, *size[k]) for k, m in masks.items()}


def compose(arrays: dict, shape, fl=False, fr=False, ft=False):
    """Casco visual suave: mínimo de las siluetas proyectadas. Devuelve (volumen[x,y,z], objetivos)."""
    nx, ny, nz = shape
    vol = np.ones(shape, np.float32)
    targets = []  # (array en ejes del mundo, eje de proyección)

    def add(t, axis):
        nonlocal vol
        targets.append((t, axis))
        vol = np.minimum(vol, np.expand_dims(t, axis))

    if "front" in arrays:
        add(arrays["front"][::-1].T, 2)
    if "back" in arrays:
        add(arrays["back"][::-1, ::-1].T, 2)
    if "right" in arrays:
        r = arrays["right"][::-1]
        add(r[:, ::-1] if fr else r, 0)
    if "left" in arrays:
        l = arrays["left"][::-1, ::-1]
        add(l[:, ::-1] if fl else l, 0)
    if "top" in arrays:
        t = arrays["top"]
        add((t[::-1] if ft else t).T, 1)
    return vol, targets


def _score(vol, targets) -> float:
    total = 0.0
    for t, axis in targets:
        inside = t > 0.5
        total += float(((vol.max(axis=axis) > 0.5) & inside).sum()) / max(1, int(inside.sum()))
    return total / len(targets)


def detect_orientation(masks: dict, dims, resolution: int = 48):
    """Prueba las combinaciones de volteo de las vistas laterales/superior y elige la más coherente."""
    shape, _ = grid_shape(dims, resolution)
    arrays = make_arrays(masks, shape)
    present = [k for k in ("left", "right", "top") if k in masks]
    best = []
    for flags in itertools.product((False, True), repeat=len(present)):
        kw = {"f" + {"left": "l", "right": "r", "top": "t"}[k]: v for k, v in zip(present, flags)}
        vol, targets = compose(arrays, shape, **kw)
        best.append((_score(vol, targets), sum(flags), kw))
    top = max(b[0] for b in best)
    # entre las combinaciones casi igual de coherentes se prefiere la de menos volteos
    return min((b for b in best if b[0] >= top - 0.004), key=lambda b: b[1])[2], top
