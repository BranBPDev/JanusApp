"""Análisis de una imagen de referencia -> descripción medida en texto (colores, regiones, proporciones, silueta, mapa de colores).

El modelo de IA es solo de texto: esto le da lo que se puede medir de la imagen (no «entiende» el dibujo como una persona,
pero sabe qué colores hay, dónde están y qué forma tiene la silueta)."""
import numpy as np
from PIL import Image

SIDE = 128
K = 7
GRID = (28, 12)         # columnas × filas del mapa de colores
LETTERS = "ABCDEFGH"


def _kmeans(px, k, iters=12):
    rng = np.random.default_rng(1)
    cent = px[rng.choice(len(px), k, replace=False)].astype(np.float64)
    for _ in range(iters):
        d = ((px[:, None, :] - cent[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            sel = px[lab == j]
            if len(sel):
                cent[j] = sel.mean(0)
    return cent, lab


def _hex(c):
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in c)


def analyze(path) -> str:
    img = Image.open(path)
    img.thumbnail((SIDE, SIDE))
    rgba = np.asarray(img.convert("RGBA")).astype(np.float64)
    h, w = rgba.shape[:2]
    rgb, alpha = rgba[..., :3], rgba[..., 3]
    if (alpha < 250).mean() > 0.02:
        mask, bgnote = alpha > 128, "fondo transparente"
    else:
        border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
        bg = np.median(border, axis=0)
        mask = np.sqrt(((rgb - bg) ** 2).sum(-1)) > 40
        bgnote = f"fondo {_hex(bg)}"
        if mask.mean() < 0.02 or mask.mean() > 0.98:
            mask = np.ones((h, w), bool)
            bgnote += " (no se distingue el objeto del fondo)"
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    bw, bh = x1 - x0, y1 - y0
    fill = mask[y0:y1, x0:x1].mean()
    kind = "circular/elíptica" if 0.70 < fill < 0.84 else ("rectangular" if fill > 0.90 else "irregular")
    sub, m = rgb[y0:y1, x0:x1], mask[y0:y1, x0:x1]
    px = sub[m]
    if len(px) > 6000:
        px = px[np.random.default_rng(0).choice(len(px), 6000, replace=False)]
    cent, _ = _kmeans(px, min(K, max(2, len(np.unique(px.astype(int), axis=0)))))
    d = ((sub[:, :, None, :] - cent[None, None]) ** 2).sum(-1)
    lab = d.argmin(-1)
    lab[~m] = -1
    order = [j for j in np.argsort([-(lab == j).sum() for j in range(len(cent))]) if (lab == j).sum() > 0.01 * m.sum()]
    names = {j: LETTERS[i] for i, j in enumerate(order)}
    lines = [f"Imagen {img.width}×{img.height} px, {bgnote}. Objeto: proporción ancho/alto = {bw / bh:.2f}, silueta {kind} (relleno {fill * 100:.0f}% de su caja)."]
    lines.append("Colores (letra, color, % del objeto, caja x e y en % con y medida desde ABAJO):")
    for j in order:
        yy, xx = np.nonzero(lab == j)
        lines.append(f"  {names[j]} {_hex(cent[j])} {100 * len(yy) / m.sum():.0f}%  x {100 * xx.min() / bw:.0f}-{100 * (xx.max() + 1) / bw:.0f}  "
                     f"y {100 - 100 * (yy.max() + 1) / bh:.0f}-{100 - 100 * yy.min() / bh:.0f}")
    col = bw // 2
    strip = lab[:, max(col - 2, 0):col + 3]
    runs, prev = [], 0
    for r in range(bh):
        vals = strip[r][strip[r] >= 0]
        c = names.get(np.bincount(vals).argmax()) if len(vals) and np.bincount(vals).argmax() in names else None
        if c != prev:
            runs.append([c, r, r + 1])
            prev = c
        else:
            runs[-1][2] = r + 1
    runs = [r for r in runs if r[0] and (r[2] - r[1]) / bh > 0.015]
    lines.append("De arriba a abajo por el centro: " + ", ".join(f"{c} ({100 * (b - a) / bh:.0f}%)" for c, a, b in runs) + ".")
    flip = m[:, ::-1]
    lines.append(f"Simetría izquierda-derecha de la silueta: {(m == flip).mean() * 100:.0f}%.")
    gc, gr = GRID
    rows = []
    for r in range(gr):
        row = ""
        for c in range(gc):
            blk = lab[r * bh // gr:max((r + 1) * bh // gr, r * bh // gr + 1), c * bw // gc:max((c + 1) * bw // gc, c * bw // gc + 1)]
            v = blk[blk >= 0]
            row += names.get(int(np.bincount(v).argmax()), ".") if len(v) > blk.size * 0.4 else "."
        rows.append(row)
    lines.append("Mapa de colores (arriba = arriba):\n" + "\n".join(rows))
    return "\n".join(lines)
