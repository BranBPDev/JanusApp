from pathlib import Path

import numpy as np
from PIL import Image

NAMES = ("movable", "fixed")   # tapa (pieza móvil) y base (pieza fija)
MAX_CELL = 512


class Interior:
    """Texturas interiores opcionales (una por pieza). Sin imagen, el interior sigue siendo de color plano.

    Cada imagen se proyecta en plano sobre el interior de su pieza, mirando hacia el corte: eje horizontal = X del
    objeto, eje vertical = profundidad (el frente queda abajo, como en la vista 'arriba'). La imagen se estira al
    ancho × fondo del objeto, de modo que un círculo inscrito en ella coincide con el borde del corte."""

    def __init__(self, images: dict = None):
        self.images = {n: (images or {}).get(n) for n in NAMES}
        self.cells = {}        # nombre -> (x0, y0, lado) en píxeles de la textura final
        self.size = None       # (ancho, alto) de la textura final

    @classmethod
    def load(cls, paths: dict = None):
        images = {}
        for name in NAMES:
            p = (paths or {}).get(name)
            if p:
                images[name] = np.asarray(Image.open(Path(p)).convert("RGBA"), np.uint8)
        return cls(images)

    def has(self, name: str) -> bool:
        return self.images.get(name) is not None

    @property
    def any(self) -> bool:
        return any(self.has(n) for n in NAMES)

    def used(self) -> dict:
        return {n: self.has(n) for n in NAMES}

    def attach(self, texture: np.ndarray, flat: dict = None, widen: bool = False):
        """Añade bajo la textura una celda cuadrada por pieza (la imagen, o el color plano si no hay).
        Devuelve (textura nueva, factor de escala (u, v) que hay que aplicar a las UV de la textura original)."""
        h, w = texture.shape[:2]
        side = min(MAX_CELL, w // 2)
        if widen:
            side = max(side, 256)
        width = max(w, 2 * side)
        out = np.full((h + side, width, 4), 255, np.uint8)
        out[:h, :w] = texture
        self.cells = {}
        for i, name in enumerate(NAMES):
            x0 = i * side
            base = np.array((flat or {}).get(name, (205, 205, 210)), np.float64)
            cell = np.empty((side, side, 4), np.uint8)
            cell[..., :3] = np.clip(base, 0, 255).astype(np.uint8)
            cell[..., 3] = 255
            if self.has(name):
                img = Image.fromarray(self.images[name], "RGBA").resize((side, side), Image.LANCZOS)
                over = Image.alpha_composite(Image.fromarray(cell, "RGBA"), img)
                cell = np.asarray(over, np.uint8).copy()
                cell[..., 3] = 255
            out[h:h + side, x0:x0 + side] = cell
            self.cells[name] = (x0, h, side)
        self.size = (width, h + side)
        return out, (w / width, h / (h + side))

    def flat_uv(self, name: str):
        x0, y0, s = self.cells[name]
        return ((x0 + s / 2) / self.size[0], (y0 + s / 2) / self.size[1])

    def remap(self, uvs, kind, V, F, name, normal, point, ext_xz):
        """Sustituye las UV de las caras interiores (kind == 1) de la pieza 'name' por la proyección plana de su imagen."""
        if not self.has(name) or name not in self.cells or not (kind == 1).any():
            return uvs
        n = np.asarray(normal, np.float64)
        n = n / max(np.linalg.norm(n), 1e-12)
        e1 = np.array([1.0, 0.0, 0.0])
        e2 = np.array([0.0, 0.0, 1.0]) - n * n[2]
        e2 = e2 / max(np.linalg.norm(e2), 1e-12)
        sel = kind == 1
        rel = V[F[sel]] - np.asarray(point, np.float64)
        u = np.clip((rel @ e1) / max(ext_xz[0], 1e-9) + 0.5, 0, 1)
        v = np.clip((rel @ e2) / max(ext_xz[1], 1e-9) + 0.5, 0, 1)
        x0, y0, s = self.cells[name]
        uvs = uvs.copy()
        uvs[sel, :, 0] = (x0 + 0.5 + u * (s - 1)) / self.size[0]
        uvs[sel, :, 1] = (y0 + 0.5 + v * (s - 1)) / self.size[1]
        return uvs
