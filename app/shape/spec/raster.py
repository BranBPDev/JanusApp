"""Dibujo de las capas del JSON: máscaras, texturas, sombreado y contornos. Todo trabaja sobre un Frame (zona en metros)."""
import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw

from app.shape.geometry.relief import view_points, visible_faces
from app.shape.spec.schema import parse_color

SS = 2   # supermuestreo del dibujo


@dataclass(frozen=True)
class Frame:
    """Zona rectangular del plano (metros, y hacia arriba) dibujada a 'k' píxeles por metro."""
    ox: float
    oy: float
    w: int
    h: int
    k: float

    def px(self, p, scale=1.0):
        return (p[0] - self.ox) * self.k * scale, (self.h - (p[1] - self.oy) * self.k) * scale

    def meters(self, xs, ys):
        return xs / self.k + self.ox, (self.h - ys) / self.k + self.oy

    @classmethod
    def around(cls, width_m, height_m, margin_px, ppm, ss=SS):
        """Cuadro (0..ancho, 0..alto) a 'ppm' píxeles por metro con un margen en píxeles (sirve para detectar siluetas que se salen)."""
        w, h = round(width_m * ppm), round(height_m * ppm)
        return cls(-margin_px / ppm, -margin_px / ppm, (w + 2 * margin_px) * ss, (h + 2 * margin_px) * ss, ppm * ss)

    @classmethod
    def square(cls, side_m, pixels, ss=SS):
        return cls(0.0, 0.0, pixels * ss, pixels * ss, pixels * ss / side_m)


def shape_mask(layer, frame: Frame):
    """Máscara booleana (frame.h, frame.w) de una forma ({'forma', ...} de una capa, una marca de saliente...)."""
    img = Image.new("L", (frame.w, frame.h), 0)
    d = ImageDraw.Draw(img)
    f = layer.get("forma", "circulo")
    if f in ("circulo", "elipse"):
        rx, ry = (layer["radio"],) * 2 if f == "circulo" else layer["radios"]
        cx, cy = frame.px(layer["centro"])
        d.ellipse([cx - rx * frame.k, cy - ry * frame.k, cx + rx * frame.k, cy + ry * frame.k], fill=255)
    elif f == "rect":
        (x0, y0), (w, h) = layer["esquina"], layer["tamano"]
        a, b = frame.px((x0, y0 + h)), frame.px((x0 + w, y0))
        r = layer.get("radio_esquina", 0) * frame.k
        if r > 0:
            d.rounded_rectangle([a[0], a[1], b[0], b[1]], radius=r, fill=255)
        else:
            d.rectangle([a[0], a[1], b[0], b[1]], fill=255)
    elif f == "poligono":
        d.polygon([frame.px(p) for p in layer["puntos"]], fill=255)
    else:                                                            # linea
        width = max(1, round(layer.get("grosor", 0.002) * frame.k))
        pts = [frame.px(p) for p in layer["puntos"]]
        d.line(pts, fill=255, width=width, joint="curve")
        for x, y in pts:
            d.ellipse([x - width / 2, y - width / 2, x + width / 2, y + width / 2], fill=255)
    mask = np.asarray(img) > 127
    if "recorte" in layer:
        x0, y0, x1, y1 = layer["recorte"]
        a, b = frame.px((x0, y1)), frame.px((x1, y0))
        keep = np.zeros_like(mask)
        keep[max(0, int(round(a[1]))):max(0, int(round(b[1]))) + 1, max(0, int(round(a[0]))):max(0, int(round(b[0]))) + 1] = True
        mask &= keep
    return mask


def _noise(xs, ys, seed):
    """Ruido de valor 2D suave (0..1) en coordenadas de red (1 unidad = una celda)."""
    g = np.random.default_rng(seed).random((64, 64)).astype(np.float32)
    x0, y0 = np.floor(xs).astype(int), np.floor(ys).astype(int)
    fx, fy = xs - x0, ys - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    at = lambda dx, dy: g[(y0 + dy) % 64, (x0 + dx) % 64]
    return (at(0, 0) * (1 - fx) + at(1, 0) * fx) * (1 - fy) + (at(0, 1) * (1 - fx) + at(1, 1) * fx) * fy


def paint(texture, frame: Frame, box):
    """Color (alto, ancho, 3) de una textura sobre la zona 'box' = (x0, y0, x1, y1) (píxeles, incluidos) del frame."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0 + 1, y1 - y0 + 1
    if "color" in texture:
        return np.broadcast_to(np.array(texture["color"], np.float32), (h, w, 3))
    yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1].astype(np.float32)
    if texture.get("radial"):
        t = np.clip(np.hypot(xx - (x0 + x1) / 2, yy - (y0 + y1) / 2) / max(w, h) * 2, 0, 1)[..., None]
        return np.array(texture["desde"], np.float32) * (1 - t) + np.array(texture["hasta"], np.float32) * t
    if "desde" in texture:
        ang = math.radians(texture["angulo"])
        d = np.array([math.cos(ang), -math.sin(ang)])                  # 90° = hacia arriba en pantalla
        half = max(abs(d[0]) * w / 2 + abs(d[1]) * h / 2, 1e-6)
        t = np.clip(((xx - (x0 + x1) / 2) * d[0] + (yy - (y0 + y1) / 2) * d[1]) / (2 * half) + 0.5, 0, 1)[..., None]
        return np.array(texture["desde"], np.float32) * (1 - t) + np.array(texture["hasta"], np.float32) * t
    mx, my = frame.meters(xx, yy)                                       # veta: estrías verticales onduladas, en metros
    u, s = mx / texture["escala"], texture["semilla"]
    g = np.sin(2 * np.pi * (u + (_noise(u * 0.7, my / texture["escala"] * 0.12, s) - 0.5) * 0.9)) * 0.5 + 0.5
    t = np.clip(g ** 4 * 0.7 + (_noise(u * 0.5, my / texture["escala"] * 0.25, s + 7) - 0.5) * 0.4, 0, 1)[..., None]
    return np.array(texture["claro"], np.float32) * (1 - t) + np.array(texture["oscuro"], np.float32) * t


def _sphere_factor(layer, frame, light, box):
    """Factor de brillo (alto, ancho de 'box') de un círculo/elipse sombreado como una esfera, con la luz respecto a la cámara."""
    (cx, cy), (rx, ry) = frame.px(layer["centro"]), [r * frame.k for r in ((layer["radio"],) * 2 if layer["forma"] == "circulo" else layer["radios"])]
    yy, xx = np.mgrid[box[1]:box[3] + 1, box[0]:box[2] + 1].astype(np.float32)
    a, b = (xx - cx) / rx, -(yy - cy) / ry
    c = np.sqrt(np.clip(1 - a * a - b * b, 0, 1))
    L = np.array(light.get("luz", [-0.45, 0.6, 0.65]), np.float32)
    L /= np.linalg.norm(L)
    lam = np.clip(a * L[0] + b * L[1] + c * L[2], 0, 1)
    return float(light.get("base", 0.66)) + float(light.get("intensidad", 0.4)) * lam


def _window_count(mask, r):
    """Cuántos píxeles de la máscara hay en la ventana cuadrada de lado 2r+1 alrededor de cada píxel (imagen integral)."""
    c = np.pad(mask.astype(np.int32), ((r + 1, r), (r + 1, r))).cumsum(axis=0).cumsum(axis=1)
    k = 2 * r + 1
    return c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]


def edge(mask, px):
    """Anillo de unos 'px' píxeles a cada lado del borde de la máscara."""
    r = max(1, int(round(px)))
    count = _window_count(mask, r)
    return (count > 0) & (count < (2 * r + 1) ** 2)


def draw_layers(textures, light, layers, frame: Frame):
    """(rgb float (h, w, 3), silueta bool) de una lista de capas, en el orden dado."""
    masks = [shape_mask(c, frame) for c in layers]
    sil = np.zeros((frame.h, frame.w), bool)
    for c, m in zip(layers, masks):
        if c.get("silueta"):
            sil |= m
    if not sil.any():
        sil[:] = True
    rgb = np.zeros((frame.h, frame.w, 3), np.float32)
    for c, m in zip(layers, masks):
        m = m & sil
        ys, xs = np.nonzero(m)
        if not len(xs):
            continue
        box = (xs.min(), ys.min(), xs.max(), ys.max())
        sub = (slice(box[1], box[3] + 1), slice(box[0], box[2] + 1))
        color = paint(textures[c["textura"]], frame, box)
        if c.get("sombrear") and c.get("forma") in ("circulo", "elipse"):
            color = np.clip(color * _sphere_factor(c, frame, light, box)[..., None], 0, 255)
        rgb[sub][m[sub]] = color[m[sub]]
        if "borde" in c:
            e = edge(m, c["borde"].get("grosor_m", 0.001) * frame.k / 2) & sil
            rgb[e] = parse_color(c["borde"].get("color", "#000000"), "borde")
    return rgb, sil


def draw_reliefs(meshes, key, dims, frame: Frame):
    """(máscara, rgb) de los relieves vistos desde la vista 'key': las caras que miran a la cámara, de lejos a cerca, con un
    poco de sombreado según lo que miran de frente. None si no hay relieves."""
    if not meshes:
        return None
    img, msk = Image.new("RGB", (frame.w, frame.h), (0, 0, 0)), Image.new("L", (frame.w, frame.h), 0)
    di, dm = ImageDraw.Draw(img), ImageDraw.Draw(msk)
    for m in meshes:
        xy, depth = view_points(key, m.V, dims)
        faces = m.F[visible_faces(m, key)]
        for f in faces[np.argsort(depth[faces].mean(axis=1))]:
            pts = [frame.px(xy[i]) for i in f]
            n = np.cross(m.V[f[1]] - m.V[f[0]], m.V[f[2]] - m.V[f[0]])
            shade = 0.72 + 0.28 * min(1.0, abs(n[{"front": 2, "back": 2, "right": 0, "left": 0, "top": 1, "bottom": 1}[key]]) / (np.linalg.norm(n) + 1e-12))
            di.polygon(pts, fill=tuple(int(c * shade) for c in m.color))
            dm.polygon(pts, fill=255)
    mask = np.asarray(msk) > 127
    return (mask, np.asarray(img).astype(np.float32)) if mask.any() else None


def downsample(rgb, alpha, ss=SS):
    """Reduce 'ss' veces con el color ponderado por la opacidad. Devuelve RGBA uint8."""
    h, w = alpha.shape[0] // ss, alpha.shape[1] // ss
    a = alpha[:h * ss, :w * ss].astype(np.float32).reshape(h, ss, w, ss).mean(axis=(1, 3))
    c = (rgb[:h * ss, :w * ss] * alpha[:h * ss, :w * ss, None]).reshape(h, ss, w, ss, 3).mean(axis=(1, 3))
    c = np.where(a[..., None] > 1e-4, c / np.maximum(a[..., None], 1e-4), 0)
    return np.dstack([np.clip(c, 0, 255), a * 255]).astype(np.uint8)
