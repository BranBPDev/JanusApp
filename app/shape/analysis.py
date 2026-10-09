import numpy as np


def _dark_mask(rgba: np.ndarray, mask: np.ndarray):
    lum = rgba[..., :3].astype(np.float64) @ np.array([0.299, 0.587, 0.114])
    thr = min(0.35 * float(np.median(lum[mask])), 60.0)
    return (lum < thr) & mask


def detect_seam(rgba: np.ndarray, mask: np.ndarray):
    """Junta: franja oscura y fina que cruza horizontalmente todo el objeto. Devuelve (centro desde arriba 0-1, grosor) o None."""
    h = mask.shape[0]
    dark = _dark_mask(rgba, mask)
    count = mask.sum(axis=1)
    wide = count >= 0.35 * count.max()
    is_seam = wide & (dark.sum(axis=1) / np.maximum(count, 1) >= 0.6)
    best, i = None, 0
    while i < h:
        if not is_seam[i]:
            i += 1
            continue
        j = i
        while j + 1 < h and is_seam[j + 1]:
            j += 1
        center, thick = (i + j + 1) / 2 / h, (j - i + 1) / h
        if 0.25 <= center <= 0.75 and 0.01 <= thick <= 0.2 and (best is None or abs(center - 0.5) < abs(best[0] - 0.5)):
            best = (center, thick)
        i = j + 1
    return best


def find_seam(images: dict, masks: dict):
    """La junta debe verse a la misma altura en al menos dos vistas laterales (no basta una raya de la textura)."""
    found = []
    for key in ("front", "back", "left", "right"):
        if key in masks:
            seam = detect_seam(images[key], masks[key])
            if seam:
                found.append(seam)
    if len(found) < 2:
        return None
    centers = [c for c, _ in found]
    if max(centers) - min(centers) > 0.04:
        return None
    return float(np.median(centers))
