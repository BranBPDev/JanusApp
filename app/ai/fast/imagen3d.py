"""Objeto a partir de imágenes de referencia: cada imagen con nombre de vista (frente, lateral, detrás, arriba…) se convierte en la
silueta y las manchas de color de esa vista del JSON; la forma 3D la calcula después la aplicación con esas vistas.

No «entiende» el dibujo: quita el fondo, traza el contorno, agrupa los colores y los coloca como capas de polígonos. Todo en numpy +
Pillow, en una fracción de segundo por imagen."""
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from app.ai.assistant import vision
from app.ai.fast import malla3d
from app.shape.spec.schema import FORMAT, SpecError

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".jfif", ".bmp", ".webp", ".gif", ".tif", ".tiff", ".tga"}
VECTOR_EXT = {".svg"}
SIDE = 360                  # lado mayor al que se reduce cada imagen para analizarla
CLUSTERS = 14
MERGE_DIST = 24.0           # dos colores más cerca que esto (RGB) se funden
MIN_BLOB = 0.0006            # una mancha de color debe cubrir al menos esta fracción de la silueta
MAX_LAYERS = 220
DEFAULT_HEIGHT = 0.3
ORGANIC = 3.0                # redondeo de las secciones del volumen (el casco visual de unas siluetas es muy anguloso)
DEPTH_GUESS = 0.7           # fondo / ancho cuando solo hay una vista
VIEWS = ("frente", "detras", "izquierda", "derecha", "arriba", "abajo")
WORDS = {"detras": ("detras", "atras", "back", "trasera", "posterior", "rear", "espalda"),
         "frente": ("frente", "front", "frontal", "delante", "delantera"),
         "izquierda": ("izquierda", "izq", "left"), "derecha": ("derecha", "der", "right"),
         "lateral": ("lateral", "side", "perfil", "costado"),
         "arriba": ("arriba", "top", "superior", "cenital"), "abajo": ("abajo", "bottom", "inferior")}
SHORT = {"der", "izq", "top"}


def _plain(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def view_of(path) -> str:
    """Vista que indica el nombre del archivo ('' si no dice ninguna; 'lateral' si no dice el lado)."""
    tokens = re.findall(r"[a-z]+", _plain(Path(path).stem))
    for view, words in WORDS.items():
        for t in tokens:
            for w in words:
                if t == w or (len(w) >= 4 and w in t):
                    return view
    return ""


# ---------------------------------------------------------------- SVG mínimo ----------
def _num_list(s):
    return [float(x) for x in re.findall(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?", s)]


def _flatten(d):
    """Subtrazados (listas de puntos) de un atributo 'd' de SVG: M L H V C S Q T Z, relativos o absolutos (los arcos se unen en recta)."""
    out, cur, start, last_c = [], (0.0, 0.0), (0.0, 0.0), None
    sub = []
    for cmd, args in re.findall(r"([MmLlHhVvCcSsQqTtAaZz])([^MmLlHhVvCcSsQqTtAaZz]*)", d):
        a = _num_list(args)
        rel = cmd.islower()
        c = cmd.upper()
        if c == "Z":
            if sub:
                sub.append(start)
                out.append(sub)
            sub, cur = [], start
            continue
        i = 0
        step = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}[c]
        while i + step <= len(a):
            p = a[i:i + step]
            i += step
            ox, oy = cur if rel else (0.0, 0.0)
            if c in "ML":
                cur = (p[0] + ox, p[1] + oy)
                if c == "M" and i == step:
                    if sub:
                        out.append(sub)
                    sub, start = [cur], cur
                else:
                    sub.append(cur)
                last_c = None
            elif c == "H":
                cur = (p[0] + (cur[0] if rel else 0), cur[1])
                sub.append(cur)
            elif c == "V":
                cur = (cur[0], p[0] + (cur[1] if rel else 0))
                sub.append(cur)
            elif c in "CS":
                if c == "C":
                    p1, p2, p3 = (p[0] + ox, p[1] + oy), (p[2] + ox, p[3] + oy), (p[4] + ox, p[5] + oy)
                else:
                    p1 = (2 * cur[0] - last_c[0], 2 * cur[1] - last_c[1]) if last_c else cur
                    p2, p3 = (p[0] + ox, p[1] + oy), (p[2] + ox, p[3] + oy)
                for t in np.linspace(0, 1, 9)[1:]:
                    u = 1 - t
                    sub.append((u ** 3 * cur[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                                u ** 3 * cur[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
                last_c, cur = p2, p3
            elif c in "QT":
                if c == "Q":
                    p1, p2 = (p[0] + ox, p[1] + oy), (p[2] + ox, p[3] + oy)
                else:
                    p1, p2 = cur, (p[0] + ox, p[1] + oy)
                for t in np.linspace(0, 1, 7)[1:]:
                    u = 1 - t
                    sub.append((u * u * cur[0] + 2 * u * t * p1[0] + t * t * p2[0], u * u * cur[1] + 2 * u * t * p1[1] + t * t * p2[1]))
                cur = p2
            else:                                              # arco: recta hasta el final
                cur = (p[5] + ox, p[6] + oy)
                sub.append(cur)
    if sub:
        out.append(sub)
    return out


def _style(el):
    st = dict(re.findall(r"([\w-]+)\s*:\s*([^;]+)", el.get("style", "")))
    return lambda k, d=None: el.get(k, st.get(k, d))


def _color(v):
    if not v or v in ("none", "transparent"):
        return None
    try:
        from PIL import ImageColor
        return ImageColor.getrgb(v.strip())
    except ValueError:
        return None


def rasterize_svg(path, side=600) -> Image.Image:
    """Dibuja un SVG sencillo (path, polyline, polygon, rect, circle, ellipse, line; rellenos y trazos, sin transformaciones)."""
    try:
        root = ET.fromstring(Path(path).read_bytes())
    except ET.ParseError:
        text = re.sub(r"<!DOCTYPE[^\[>]*(\[.*?\])?\s*>", "", Path(path).read_text(encoding="utf-8", errors="ignore"), flags=re.S)
        text = re.sub(r"&\w+;", "", text)
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            raise SpecError(f"No he podido leer {Path(path).name} como SVG.")
    vb = _num_list(root.get("viewBox", "")) or [0, 0, _num_list(root.get("width", "100"))[0], _num_list(root.get("height", "100"))[0]]
    k = side / max(vb[2], vb[3])
    img = Image.new("RGBA", (max(1, round(vb[2] * k)), max(1, round(vb[3] * k))), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    P = lambda pts: [((x - vb[0]) * k, (y - vb[1]) * k) for x, y in pts]
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        g = _style(el)
        fill, stroke = _color(g("fill", "black")), _color(g("stroke"))
        sw = max(1, round(float(_num_list(g("stroke-width", "1"))[0] if _num_list(g("stroke-width", "1")) else 1) * k))
        shapes = []
        if tag == "path":
            shapes = _flatten(el.get("d", ""))
        elif tag in ("polyline", "polygon"):
            v = _num_list(el.get("points", ""))
            shapes = [list(zip(v[0::2], v[1::2]))]
        elif tag == "rect":
            x, y, w, h = (float(el.get(a, 0)) for a in ("x", "y", "width", "height"))
            shapes = [[(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]]
        elif tag in ("circle", "ellipse"):
            cx, cy = float(el.get("cx", 0)), float(el.get("cy", 0))
            rx = float(el.get("r", el.get("rx", 0)))
            ry = float(el.get("r", el.get("ry", 0)))
            shapes = [[(cx + rx * np.cos(t), cy + ry * np.sin(t)) for t in np.linspace(0, 2 * np.pi, 40)]]
        elif tag == "line":
            shapes = [[(float(el.get("x1", 0)), float(el.get("y1", 0))), (float(el.get("x2", 0)), float(el.get("y2", 0)))]]
        for pts in shapes:
            if len(pts) < 2:
                continue
            xy = P(pts)
            if fill and len(pts) > 2:
                d.polygon(xy, fill=fill + (255,))
            if stroke:
                d.line(xy, fill=stroke + (255,), width=sw)
    return img


def open_image(path) -> Image.Image:
    p = Path(path)
    if p.suffix.lower() in VECTOR_EXT:
        return rasterize_svg(p)
    im = Image.open(p)
    im.load()
    return im


# ---------------------------------------------------------------- máscara y contorno ----------
def _grow(bg, free):
    grow = bg.copy()
    grow[1:] |= bg[:-1]
    grow[:-1] |= bg[1:]
    grow[:, 1:] |= bg[:, :-1]
    grow[:, :-1] |= bg[:, 1:]
    return grow & free


def _flood(seed, free):
    bg = seed & free
    for _ in range(sum(free.shape)):
        nxt = _grow(bg, free)
        if (nxt == bg).all():
            break
        bg = nxt
    return bg


def _otsu(values, lo, hi):
    hist, edges = np.histogram(values, bins=48, range=(0, max(values.max(), 1)))
    best, thr, w0, s0, tot, sum_all = 0.0, lo, 0.0, 0.0, hist.sum(), (hist * (edges[:-1] + edges[1:]) / 2).sum()
    for h, a, b in zip(hist, edges[:-1], edges[1:]):
        w0 += h
        s0 += h * (a + b) / 2
        if w0 == 0 or w0 == tot:
            continue
        var = w0 * (tot - w0) * (s0 / w0 - (sum_all - s0) / (tot - w0)) ** 2
        if var > best:
            best, thr = var, b
    return float(min(max(thr * 0.6, lo), hi))


def _label(mask):
    """(etiquetas, cuántas): componentes conexas (8 vecinos) de una máscara."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    n = 0
    for y, x in zip(*np.nonzero(mask)):
        if lab[y, x]:
            continue
        n += 1
        lab[y, x] = n
        q = deque([(y, x)])
        while q:
            cy, cx = q.popleft()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = n
                        q.append((ny, nx))
    return lab, n


def _largest(mask):
    lab, n = _label(mask)
    if n <= 1:
        return mask
    sizes = np.bincount(lab.ravel())[1:]
    return lab == (1 + int(sizes.argmax()))


def object_mask(im: Image.Image):
    """(rgb float (h,w,3), máscara booleana) del objeto de una imagen, recortado a su caja: usa la transparencia si la hay y, si no,
    quita el fondo (el color del borde, conectado con el borde)."""
    im = im.convert("RGBA")
    im.thumbnail((SIDE, SIDE))
    arr = np.asarray(im).astype(np.float32)
    rgb, alpha = arr[..., :3], arr[..., 3]
    if (alpha < 200).mean() > 0.02:
        mask = alpha >= 128
    else:
        ring = np.concatenate([rgb[:2].reshape(-1, 3), rgb[-2:].reshape(-1, 3), rgb[:, :2].reshape(-1, 3), rgb[:, -2:].reshape(-1, 3)])
        bgc = np.median(ring, axis=0)
        dist = np.sqrt(((rgb - bgc) ** 2).sum(-1))
        thr = _otsu(dist[dist > 0] if (dist > 0).any() else dist, 16, 70)
        seed = np.zeros(dist.shape, bool)
        seed[0, :] = seed[-1, :] = seed[:, 0] = seed[:, -1] = True
        mask = ~_flood(seed, dist < thr)
    mask = _largest(mask)
    ys, xs = np.nonzero(mask)
    if len(xs) < 80:
        raise SpecError("No distingo el objeto del fondo en una de las imágenes.")
    sl = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
    return rgb[sl], mask[sl]


# ---------------------------------------------------------------- hojas con varias vistas ----------
SHEET_ORDER = ("frente", "izquierda", "arriba", "detras", "abajo")     # orden habitual de una hoja de vistas, de izquierda a derecha
SHEET_MIN_ASPECT = 1.5


def _dilate(m, n):
    for _ in range(n):
        g = m.copy()
        g[1:] |= m[:-1]
        g[:-1] |= m[1:]
        g[:, 1:] |= m[:, :-1]
        g[:, :-1] |= m[:, 1:]
        m = g
    return m


def split_sheet(im: Image.Image):
    """Si la imagen es una hoja con varias vistas una al lado de otra (fondo claro, cuadrícula y textos), devuelve
    [(vista, imagen RGBA recortada con transparencia, (ancho_px, alto_px) a la escala de la hoja)] de izquierda a derecha; si no, []."""
    im = im.convert("RGB")
    if im.width / im.height < SHEET_MIN_ASPECT:
        return []
    k = max(1, round(max(im.size) / 700))
    small = im.resize((im.width // k, im.height // k))
    a = np.asarray(small).astype(np.int16)
    mx, mn = a.max(-1), a.min(-1)
    bg = (mn > 200) & (mx - mn < 60)                         # blanco, cuadrícula pálida
    sat = (mx - mn) / np.maximum(mx, 1)
    core = (sat > 0.22) & ~bg
    lab, n = _label(_dilate(core, 3))
    if n == 0:
        return []
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    boxes = []
    for i in range(1, n + 1):
        if sizes[i] < 0.004 * lab.size:
            continue
        ys, xs = np.nonzero(lab == i)
        boxes.append([xs.min(), xs.max(), [i]])
    boxes.sort()
    groups = []
    for b in boxes:                                          # lo que se solapa en horizontal es la misma vista
        if groups and b[0] <= groups[-1][1]:
            groups[-1][1] = max(groups[-1][1], b[1])
            groups[-1][2] += b[2]
        else:
            groups.append(b)
    if len(groups) < 2 or len(groups) > len(SHEET_ORDER):
        return []
    out = []
    for view, (x0, x1, ids) in zip(SHEET_ORDER, groups):
        region = np.isin(lab, ids)
        mask = region & ~bg
        filled = ~_flood(_edge(mask), ~mask)                   # rellena los huecos cerrados (ojos, interior)
        ys, xs = np.nonzero(filled)
        if len(xs) < 80:
            return []
        # a resolución completa: sube la máscara y recorta
        full = np.asarray(Image.fromarray((filled * 255).astype(np.uint8)).resize(im.size, Image.NEAREST)) > 127
        fy, fx = np.nonzero(full)
        sl = (slice(fy.min(), fy.max() + 1), slice(fx.min(), fx.max() + 1))
        rgba = np.dstack([np.asarray(im)[sl], (full[sl] * 255).astype(np.uint8)])
        out.append((view, Image.fromarray(rgba, "RGBA"), (rgba.shape[1], rgba.shape[0])))
    return out


def _edge(mask):
    e = np.zeros_like(mask)
    e[0, :] = e[-1, :] = e[:, 0] = e[:, -1] = True
    return e


_RING = ((0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1))


def outline(mask):
    """Contorno exterior de una máscara conexa como lista de (x, y) en píxeles (seguimiento de Moore)."""
    m = np.pad(mask, 1)
    ys, xs = np.nonzero(m)
    s = (int(ys[0]), int(xs[0]))
    c, d, seen, pts = s, 0, set(), []
    while (c, d) not in seen:
        seen.add((c, d))
        pts.append((c[1] - 1, c[0] - 1))
        for k in range(1, 9):
            dy, dx = _RING[(d + k) % 8]
            if m[c[0] + dy, c[1] + dx]:
                break
        else:
            break
        pdy, pdx = _RING[(d + k - 1) % 8]
        n = (c[0] + dy, c[1] + dx)
        d = _RING.index((c[0] + pdy - n[0], c[1] + pdx - n[1]))
        c = n
    return pts


def _rdp(p, eps):
    if len(p) < 3:
        return p
    a, b = p[0], p[-1]
    ab = b - a
    n = np.hypot(*ab)
    dv = p[1:-1] - a
    dist = np.abs(ab[0] * dv[:, 1] - ab[1] * dv[:, 0]) / n if n > 1e-9 else np.hypot(dv[:, 0], dv[:, 1])
    i = int(dist.argmax())
    if dist[i] <= eps:
        return np.array([a, b])
    left, right = _rdp(p[:i + 2], eps), _rdp(p[i + 1:], eps)
    return np.vstack([left[:-1], right])


def simplify(pts, cap, eps=0.7):
    """Polígono cerrado simplificado a lo sumo a 'cap' puntos."""
    p = np.array(pts, float)
    if len(p) <= 4:
        return p
    far = int(np.hypot(*(p - p[0]).T).argmax())
    while True:
        a = _rdp(p[:far + 1], eps)
        b = _rdp(np.vstack([p[far:], p[:1]]), eps)
        poly = np.vstack([a[:-1], b[:-1]])
        if len(poly) <= cap or eps > 30:
            return poly
        eps *= 1.3


# ---------------------------------------------------------------- colores ----------
def _smooth(lab, k):
    out = lab
    for _ in range(2):
        counts = np.zeros((k,) + lab.shape, np.int16)
        pad = np.pad(out, 1, mode="edge")
        for dy in range(3):
            for dx in range(3):
                win = pad[dy:dy + lab.shape[0], dx:dx + lab.shape[1]]
                for j in range(k):
                    counts[j] += (win == j)
        out = counts.argmax(0)
    return out


def color_regions(rgb, mask):
    """(colores, etiquetas): colores dominantes del objeto (se funden los parecidos) y el color de cada píxel (-1 fuera)."""
    px = rgb[mask]
    sample = px if len(px) <= 5000 else px[np.random.default_rng(0).choice(len(px), 5000, replace=False)]
    k = max(2, min(CLUSTERS, len(np.unique(sample.astype(int), axis=0))))
    cent, _ = vision._kmeans(sample, k)
    dist = ((rgb[:, :, None, :] - cent[None, None]) ** 2).sum(-1)
    lab = dist.argmin(-1)
    lab[~mask] = 0
    lab = _smooth(lab, k)
    lab[~mask] = -1
    share = np.array([(lab == j).sum() for j in range(k)])
    alive = [j for j in range(k) if share[j] > 0]
    for _ in range(k):                                   # funde los colores muy parecidos en el más grande
        pair = None
        for a in alive:
            for b in alive:
                if a < b and np.linalg.norm(cent[a] - cent[b]) < MERGE_DIST:
                    pair = (a, b) if share[a] >= share[b] else (b, a)
        if not pair:
            break
        keep, drop = pair
        lab[lab == drop] = keep
        share[keep] += share[drop]
        share[drop] = 0
        alive.remove(drop)
    colors = []
    remap = {}
    for j in sorted(alive, key=lambda j: -share[j]):
        sel = lab == j
        remap[j] = len(colors)
        colors.append(rgb[sel].mean(0))
    out = np.full(lab.shape, -1, np.int32)
    for j, i in remap.items():
        out[lab == j] = i
    return colors, out


# ---------------------------------------------------------------- vista → capas ----------
def _hex(c):
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in c)


def view_layers(im, prefix, w_m=None, h_m=None):
    """(texturas, capas, relación ancho/alto) de una imagen. Si se dan w_m y h_m se escala a esa caja; si no, a alto 1."""
    rgb, mask = object_mask(im)
    H, W = mask.shape
    colors, lab = color_regions(rgb, mask)
    ratio = W / H
    w_m, h_m = (w_m, h_m) if w_m else (ratio, 1.0)
    sx, sy = w_m / max(W - 1, 1), h_m / max(H - 1, 1)
    conv = lambda poly: [[round(float(x * sx), 5), round(float((H - 1 - y) * sy), 5)] for x, y in poly]
    textures = {f"{prefix}{i + 1}": {"color": _hex(c)} for i, c in enumerate(colors)}
    layers = [{"textura": f"{prefix}1", "forma": "poligono", "puntos": conv(simplify(outline(mask), 220)), "silueta": True}]
    blobs = []
    total = int(mask.sum())
    for i in range(len(colors)):
        comp, n = _label(lab == i)
        for j in range(1, n + 1):
            sel = comp == j
            area = int(sel.sum())
            if area < max(10, MIN_BLOB * total):
                continue
            ys, xs = np.nonzero(sel)
            box = (xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1)
            if i == 0 and area > 0.5 * total:            # el cuerpo del color base ya lo da la silueta
                continue
            blobs.append((box, area, i, sel))
    blobs.sort(key=lambda b: (-b[0], -b[1]))                # las grandes primero: lo pequeño se pinta encima
    kept = sorted(blobs, key=lambda b: -b[1])[:MAX_LAYERS - 1]
    for box, area, i, sel in sorted(kept, key=lambda b: (-b[0], -b[1])):
        poly = simplify(outline(sel), 90 if area > 0.05 * total else 36)
        if len(poly) >= 3:
            layers.append({"textura": f"{prefix}{i + 1}", "forma": "poligono", "puntos": conv(poly)})
    return textures, layers, ratio


# ---------------------------------------------------------------- objeto completo ----------
def assign(paths):
    """{vista: ruta} y avisos: usa el nombre del archivo; las imágenes sin nombre de vista rellenan frente y lateral si faltan."""
    chosen, spare, notes = {}, [], []
    for p in paths:
        v = view_of(p)
        if v == "lateral":
            v = "derecha" if "derecha" not in chosen else "izquierda"
        if v and v not in chosen:
            chosen[v] = p
        elif v:
            notes.append(f"{Path(p).name}: ya tengo una imagen para «{v}».")
        else:
            spare.append(p)
    for p in list(spare):
        missing = next((v for v in ("frente", "derecha") if v not in chosen and not (v == "derecha" and "izquierda" in chosen)), None)
        if missing:
            chosen[missing] = p
            spare.remove(p)
            notes.append(f"{Path(p).name}: no dice qué vista es; la tomo como «{missing}».")
    for p in spare:
        notes.append(f"{Path(p).name}: no dice qué vista es y ya tengo las necesarias; no la uso (ponle «frente», «lateral», «detras»… en el nombre).")
    return chosen, notes


def _recolor(source, mask):
    """Imagen RGBA con la forma 'mask' y los colores de 'source' = (rgb, máscara) estirados a ella (el fondo se rellena con el color del borde)."""
    from app.shape.texture.atlas import extend_colors
    rgb, smask = source
    full = extend_colors(np.dstack([rgb, np.zeros(smask.shape, np.float32)]), smask, iters=max(rgb.shape[:2]) + 5)
    img = Image.fromarray(np.clip(full, 0, 255).astype(np.uint8)).resize((mask.shape[1], mask.shape[0]), Image.LANCZOS)
    return Image.fromarray(np.dstack([np.asarray(img), (mask * 255).astype(np.uint8)]), "RGBA")


def _from_mesh(path, colors, log):
    """{vista: (imagen RGBA, (ancho_px, alto_px))} con las siluetas de un modelo 3d, pintadas con los colores de las imágenes dadas."""
    masks, ext = malla3d.silhouettes(path)
    log.append(f"{Path(path).name}: modelo 3d de {ext[0]:.1f} × {ext[2]:.1f} × {ext[1]:.1f} (ancho × alto × fondo, en unidades del archivo); la forma sale de él.")
    mean = lambda src: np.array([src[0][src[1]][:, c].mean() for c in range(3)])
    base = colors.get("frente") or next(iter(colors.values()), None)
    out = {}
    for v, mask in masks.items():
        src = colors.get(v)
        if src is None and v in ("izquierda", "derecha") and ("derecha" if v == "izquierda" else "izquierda") in colors:
            rgb, m = colors["derecha" if v == "izquierda" else "izquierda"]
            src = (rgb[:, ::-1], m[:, ::-1])                   # la otra lateral, reflejada
        if src is None and base is not None:
            src = (np.broadcast_to(mean(base), (8, 8, 3)).astype(np.float32), np.ones((8, 8), bool))
        if src is None:
            src = (np.full((8, 8, 3), (150, 170, 160), np.float32), np.ones((8, 8), bool))
        out[v] = (_recolor(src, mask), (mask.shape[1], mask.shape[0]))
    return out


def build(paths, height=None, name="objeto", width_m=None, depth_m=None):
    """(spec, cambios) de las imágenes dadas. 'height', 'width_m' y 'depth_m' en metros: el alto por defecto es 0,3 y, si no se dan,
    ancho y fondo salen de las proporciones de las imágenes; si se dan, cada vista se ajusta a esas medidas."""
    models = [p for p in paths if Path(p).suffix.lower() in malla3d.MODEL_EXT]
    files = [p for p in paths if Path(p).suffix.lower() in IMAGE_EXT | VECTOR_EXT]
    if not files and not models:
        raise SpecError("No hay imágenes ni modelos que usar: adjunta al menos una vista de frente y otra lateral (PNG, JPG, SVG…) o un modelo .stl.")
    sheet, log0 = {}, []
    for p in list(files):
        if not view_of(p):
            parts = split_sheet(open_image(p))
            if parts:
                files.remove(p)
                for v, im, size in parts:
                    sheet[v] = (im, size)
                log0.append(f"{Path(p).name}: es una hoja con {len(parts)} vistas ({', '.join(v for v, _, _ in parts)}); las separo.")
    chosen, log = assign(files)
    log = log0 + log
    chosen = {v: p for v, p in chosen.items() if v not in sheet}
    if models:                                                 # la forma sale del modelo 3d; las imágenes (si hay) aportan los colores
        colors = {v: object_mask(open_image(p)) for v, p in chosen.items()}
        colors.update({v: object_mask(im) for v, (im, _) in sheet.items()})
        sheet = _from_mesh(models[0], colors, log0)
        chosen = {}
    if not chosen and not sheet:
        raise SpecError("Ninguna imagen se puede usar como vista; ponle «frente» o «lateral» en el nombre del archivo.")
    H = float(height or DEFAULT_HEIGHT)
    ims = {v: open_image(p) for v, p in chosen.items()}
    ims.update({v: im for v, (im, _) in sheet.items()})
    ratios = {}
    for v, im in ims.items():                                  # relación ancho/alto de cada vista
        rgb, mask = object_mask(im)
        ratios[v] = mask.shape[1] / mask.shape[0]
    side = next((ratios[v] for v in ("derecha", "izquierda") if v in ratios), None)
    front = ratios.get("frente") or ratios.get("detras")
    if front:
        width = front * H
        depth = side * H if side else width * DEPTH_GUESS
    else:
        depth = side * H
        width = depth / DEPTH_GUESS
    if sheet and "frente" in sheet:                           # misma escala en toda la hoja: las medidas salen de los píxeles
        k = H / sheet["frente"][1][1]
        width = sheet["frente"][1][0] * k
        side_px = next((sheet[v][1][0] for v in ("derecha", "izquierda") if v in sheet), None)
        depth = side_px * k if side_px else width * DEPTH_GUESS
        side = depth / H
    if width_m:
        width = float(width_m)
    if depth_m:
        depth = float(depth_m)
    guessed = []
    if "frente" not in ratios and "detras" not in ratios:
        guessed.append("frente")
    if side is None:
        guessed.append("lateral")
    dims = {"frente": (width, H), "detras": (width, H), "izquierda": (depth, H), "derecha": (depth, H), "arriba": (width, depth), "abajo": (width, depth)}
    if sheet:
        k = H / sheet.get("frente", next(iter(sheet.values())))[1][1]
        for v, (_, (pw, ph)) in sheet.items():
            if v in ("frente", "detras", "izquierda", "derecha"):
                ref_w = width if v in ("frente", "detras") else depth
                dims[v] = (ref_w if abs(pw * k - ref_w) < 0.06 * ref_w else pw * k, H if abs(ph * k - H) < 0.06 * H else ph * k)
            else:                                              # cenital: ancho × fondo (se ajusta si difiere poco de las otras vistas)
                near = lambda a, b: b if abs(a - b) < 0.1 * b else a
                dims[v] = (near(pw * k, width), near(ph * k, depth))
    if width_m or depth_m:                                    # medidas pedidas: cada vista se ajusta a su caja
        for v in dims:
            w, h = dims[v]
            if v in ("frente", "detras"):
                w = width
            elif v in ("izquierda", "derecha"):
                w = depth
            else:
                w, h = width, depth
            dims[v] = (w, h)
    textures, views = {}, {}
    for v, im in ims.items():
        w, h = dims[v]
        t, layers, _ = view_layers(im, f"{v[:3]}_", w, h)
        textures.update(t)
        views[v] = {"capas": layers}
        log.append(f"{v} ← {Path(chosen[v]).name if v in chosen else "hoja"}: silueta de {len(layers[0]['puntos'])} puntos y {len(t)} colores")
    base_of = lambda v: next(iter(t for t in textures if t.startswith(f"{v[:3]}_")))
    if "frente" not in views and "detras" not in views:       # sin frontal: elipse con el color principal de la lateral
        views["frente"] = {"capas": [{"textura": base_of(next(iter(ims))), "forma": "elipse", "centro": [width / 2, H / 2], "radios": [width / 2, H / 2], "silueta": True}]}
    if not ({"izquierda", "derecha"} & set(views)):           # sin lateral: elipse con el color principal del frente
        views["derecha"] = {"capas": [{"textura": base_of("frente" if "frente" in views else next(iter(ims))), "forma": "elipse",
                                       "centro": [depth / 2, H / 2], "radios": [depth / 2, H / 2], "silueta": True}]}
    if guessed:
        log.append("Solo tengo " + ("la vista " + ", ".join(v for v in views if v not in guessed) if len(views) - len(guessed) == 1 else "algunas vistas")
                   + f": {' y '.join(guessed)} es una estimación; con una imagen de frente y otra lateral sale mejor.")
    spec = {"formato": FORMAT, "nombre": name, "medidas_m": {"ancho": round(width, 4), "alto": round(H, 4), "fondo": round(depth, 4)},
            "redondeo": ORGANIC, "texturas": textures, "vistas": views, "marcas": {}}
    log.insert(0, f"objeto desde imágenes: {width * 100:.0f} × {H * 100:.0f} × {depth * 100:.0f} cm (ancho × alto × fondo)")
    return spec, log
