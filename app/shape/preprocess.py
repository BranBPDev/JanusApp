import numpy as np
from PIL import Image

MAX_SIDE = 768


def _otsu(values: np.ndarray, bins: int = 256) -> float:
    hist, edges = np.histogram(values, bins=bins)
    hist = hist.astype(np.float64)
    centers = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m0 = np.cumsum(hist * centers)
    with np.errstate(divide="ignore", invalid="ignore"):
        between = w0 * w1 * (m0 / w0 - (m0[-1] - m0) / w1) ** 2
    return float(centers[np.argmax(np.nan_to_num(between))])


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Rellena los huecos internos de la silueta (el fondo que no toca el borde de la imagen)."""
    bg = ~mask
    reach = np.zeros_like(bg)
    reach[0, :], reach[-1, :], reach[:, 0], reach[:, -1] = bg[0, :], bg[-1, :], bg[:, 0], bg[:, -1]
    count = int(reach.sum())
    while True:
        grown = reach.copy()
        grown[1:, :] |= reach[:-1, :]
        grown[:-1, :] |= reach[1:, :]
        grown[:, 1:] |= reach[:, :-1]
        grown[:, :-1] |= reach[:, 1:]
        grown &= bg
        new_count = int(grown.sum())
        if new_count == count:
            return ~grown
        reach, count = grown, new_count


def load_silhouette(path: str):
    """Devuelve (máscara booleana recortada al objeto, aviso o None)."""
    with Image.open(path) as im:
        im = im.convert("RGBA")
    w, h = im.size
    if max(w, h) > MAX_SIDE:
        s = MAX_SIDE / max(w, h)
        im = im.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    arr = np.asarray(im, dtype=np.float32)

    alpha = arr[..., 3] / 255.0
    if (alpha < 0.5).mean() > 0.005:  # PNG con transparencia real
        mask = alpha >= 0.5
    else:  # fondo uniforme: se estima por los bordes
        rgb = arr[..., :3]
        border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
        bg = np.median(border, axis=0)
        dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))
        mask = dist > max(_otsu(dist), 12.0)

    mask = fill_holes(mask)
    coverage = float(mask.mean())
    warning = None
    if coverage > 0.92 or coverage < 0.002:
        warning = "no se pudo separar el objeto del fondo (usa un PNG con transparencia)"

    ys = np.flatnonzero(mask.any(axis=1))
    xs = np.flatnonzero(mask.any(axis=0))
    if len(ys) == 0:
        raise ValueError("la imagen no contiene ningún objeto")
    return mask[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1], warning
