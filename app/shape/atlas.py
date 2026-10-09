import numpy as np
from PIL import Image

# vista -> dirección hacia la cámara
CHARTS = {"front": (0, 0, 1), "back": (0, 0, -1), "right": (-1, 0, 0), "left": (1, 0, 0), "top": (0, 1, 0)}
GAP = 3
BLOCK = 8
NEUTRAL = np.array([205.0, 205.0, 210.0])


def extend_colors(rgba: np.ndarray, mask: np.ndarray, iters: int = 10) -> np.ndarray:
    """Rellena el fondo con el color del borde del objeto (evita halos oscuros al filtrar la textura)."""
    color = rgba[..., :3].astype(np.float32)
    valid = mask.copy()
    for _ in range(iters):
        if valid.all():
            break
        acc = np.zeros_like(color)
        cnt = np.zeros(valid.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sv = np.roll(valid, (dy, dx), axis=(0, 1))
            sc = np.roll(color, (dy, dx), axis=(0, 1))
            acc += sc * sv[..., None]
            cnt += sv
        fill = (~valid) & (cnt > 0)
        color[fill] = acc[fill] / cnt[fill][:, None]
        valid = valid | fill
    return np.clip(color, 0, 255).astype(np.uint8)


def _pow2(n: int) -> int:
    return 1 << max(5, int(np.ceil(np.log2(max(n, 1)))))


class Atlas:
    """Una sola textura con las vistas colocadas como 'charts' + bloques de color plano (interior y base)."""

    def __init__(self, images, masks, bbox, cap=256, upper_color=None, lower_color=None):
        lo, hi = bbox
        self.lo = np.asarray(lo, np.float64)
        self.ext = np.maximum(np.asarray(hi, np.float64) - self.lo, 1e-9)
        w, h, d = self.ext[0], self.ext[1], self.ext[2]
        size = {"front": (w, h), "back": (w, h), "left": (d, h), "right": (d, h), "top": (w, d)}
        keys = [k for k in CHARTS if k in images]

        s = cap / max(2 * w, 2 * d, 1.3 * w, 2 * h + d)
        for _ in range(4):  # ajusta la escala para que quepa en 'cap' píxeles
            lw = max(2 * w * s, 2 * d * s, w * s + 2 * BLOCK + 3 * GAP) + GAP
            lh = (2 * h + d) * s + 2 * GAP
            s *= min(1.0, cap / lw, cap / lh)
        px = {k: (max(4, int(round(size[k][0] * s))), max(4, int(round(size[k][1] * s)))) for k in keys}

        rows = [("front", "back"), ("left", "right"), ("top", None)]
        self.rects, y = {}, 0
        for row in rows:
            x, row_h = 0, 0
            for k in row:
                if k in px:
                    self.rects[k] = (x, y, *px[k])
                    x += px[k][0] + GAP
                    row_h = max(row_h, px[k][1])
            y += row_h + GAP
        right = max([r[0] + r[2] for r in self.rects.values()] + [0])
        bx, by = (self.rects["top"][0] + self.rects["top"][2] + GAP, self.rects["top"][1]) if "top" in self.rects \
            else (0, y)
        bottom = max([r[1] + r[3] for r in self.rects.values()] + [by + BLOCK])
        self.size = (_pow2(max(right, bx + 3 * (BLOCK + GAP))), _pow2(max(bottom, by + BLOCK)))

        tw, th = self.size
        tex = np.full((th, tw, 4), 255, np.uint8)
        for k in keys:
            ext = extend_colors(images[k], masks[k])
            x, y0, rw, rh = self.rects[k]
            tex[y0:y0 + rh, x:x + rw, :3] = np.asarray(Image.fromarray(ext).resize((rw, rh), Image.LANCZOS))

        front = images.get("front")
        under = front[-max(1, front.shape[0] // 12):, :, :3].reshape(-1, 3).mean(axis=0) if front is not None else NEUTRAL
        colors = [self._interior(c) for c in (upper_color, lower_color)] + [under]
        self.block_uv = []
        for i, c in enumerate(colors):
            x = bx + i * (BLOCK + GAP)
            tex[by:by + BLOCK, x:x + BLOCK, :3] = np.clip(c, 0, 255).astype(np.uint8)
            self.block_uv.append(((x + BLOCK / 2) / tw, (by + BLOCK / 2) / th))
        self.texture = tex
        self.keys = keys

    @staticmethod
    def _interior(mean):
        mean = NEUTRAL if mean is None else np.asarray(mean, np.float64)
        return 0.25 * mean + 0.75 * NEUTRAL

    @property
    def upper_uv(self):
        return self.block_uv[0]

    @property
    def lower_uv(self):
        return self.block_uv[1]

    def _image_uv(self, key, P):
        t = (P - self.lo) / self.ext
        x, y, z = t[..., 0], t[..., 1], t[..., 2]
        v = 1 - y
        return {"front": (x, v), "back": (1 - x, v), "right": (z, v), "left": (1 - z, v), "top": (x, z)}[key]

    def corner_uvs(self, V, F, kind, interior_uv):
        """UV por esquina de cara: las caras exteriores van al 'chart' de la vista que mejor las ve."""
        tri = V[F]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
        dirs = np.array([CHARTS[k] for k in self.keys], np.float64)
        best = np.argmax(n @ dirs.T, axis=1)
        under = (n[:, 1] < -0.5) | (kind == 2)
        uvs = np.zeros((len(F), 3, 2))
        for ci, k in enumerate(self.keys):
            sel = (best == ci) & ~under & (kind == 0)
            if not sel.any():
                continue
            u, v = self._image_uv(k, tri[sel])
            x0, y0, rw, rh = self.rects[k]
            uvs[sel, :, 0] = (x0 + 0.5 + np.clip(u, 0, 1) * (rw - 1)) / self.size[0]
            uvs[sel, :, 1] = (y0 + 0.5 + np.clip(v, 0, 1) * (rh - 1)) / self.size[1]
        flat = kind == 1
        uvs[flat] = np.array(interior_uv)
        uvs[under & ~flat] = np.array(self.block_uv[2])
        return uvs
