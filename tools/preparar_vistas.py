"""Prepara vistas y mallas para JanusApp a partir de imágenes tuyas (una por vista, cualquier tamaño, fondo liso).

  python tools/preparar_vistas.py --nombre objeto --alto 0.70 --salida testing/vistas/objeto \
      --frente f.png --detras d.png --izquierda i.png --derecha r.png --arriba a.png --abajo b.png [--huesos huesos.json]

Qué hace:
  1. Quita el fondo (color de las esquinas, con degradado) y recorta el objeto.
  2. Escala todas las vistas a la misma escala real: --alto es la altura del objeto en metros (1 cuadro de la malla = 0,05 m
     = 128 px). El fondo transparente y el objeto quedan centrados en un lienzo de 640x640.
  3. Escribe <nombre>_<vista>.png y <nombre>_<vista>_malla.png (cuadrícula a escala) con los nombres que reconoce la app.
  4. Si das --huesos, dibuja las articulaciones en las mallas (punto del color de su número con anillo del color del padre).

huesos.json (coordenadas en píxeles de TUS imágenes originales; cada hueso solo en las vistas donde lo ves):
  {"huesos": [{"id": 0, "padre": null, "frente": [320, 410], "derecha": [200, 380]},
              {"id": 1, "padre": 0,    "frente": [320, 300], "arriba": [320, 250]}]}
  Los ids van de 0 a 59; el hueso sin padre (null) es la raíz. Mínimo: cada hueso en una vista de frente/detrás (x, y)
  y en una lateral o superior (z)."""
import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

CANVAS = 640
CELL_PX = 128
CELL_M = 0.05
MARGIN = 12
VIEWS = ("frente", "detras", "izquierda", "derecha", "arriba", "abajo")
LEVELS = (125, 170, 215, 255)
PALETTE = [c for c in itertools.product(LEVELS, repeat=3) if not (c[0] == c[1] == c[2])]
GRID = (110, 110, 110, 255)


def remove_background(img, tolerance):
    """RGBA con el fondo transparente. El fondo se modela como un degradado suave ajustado al borde de la imagen y se quita
    lo que se le parece y está conectado con los bordes."""
    img = img.convert("RGBA")
    arr = np.asarray(img)
    if (arr[..., 3] < 250).mean() > 0.05:                    # ya trae transparencia
        return img
    rgb = arr[..., :3].astype(np.float64)
    h, w = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    ring = np.zeros((h, w), bool)
    ring[:4], ring[-4:], ring[:, :4], ring[:, -4:] = True, True, True, True
    u, v = xx / max(w - 1, 1), yy / max(h - 1, 1)
    basis = np.stack([np.ones_like(u), u, v, u * v], axis=-1)
    coef = np.linalg.lstsq(basis[ring], rgb[ring], rcond=None)[0]
    model = basis @ coef
    cand = np.abs(rgb - model).sum(axis=2) <= tolerance
    mask = Image.fromarray(np.where(cand[..., None], np.uint8(255), np.uint8(0)).repeat(3, axis=2), "RGB")
    for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if mask.getpixel(seed) == (255, 255, 255):
            ImageDraw.floodfill(mask, seed, (255, 0, 255), thresh=0)
    bg = np.all(np.asarray(mask) == np.array([255, 0, 255]), axis=2)
    alpha = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8), "L").filter(ImageFilter.MinFilter(3))   # sin halo
    out = arr.copy()
    out[..., 3] = np.asarray(alpha)
    return Image.fromarray(out, "RGBA")


def bbox(img):
    ys, xs = np.nonzero(np.asarray(img)[..., 3] > 40)
    if not len(xs):
        raise SystemExit("Una vista no tiene objeto visible (revisa el fondo o --tolerancia).")
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def grid_image():
    g = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    for k in range(0, CANVAS, CELL_PX):
        d.line([(k, 0), (k, CANVAS - 1)], fill=GRID)
        d.line([(0, k), (CANVAS - 1, k)], fill=GRID)
    return g


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--alto", type=float, required=True, help="altura real del objeto en metros")
    ap.add_argument("--salida", default=".")
    ap.add_argument("--tolerancia", type=int, default=28, help="diferencia de color admitida respecto al fondo")
    ap.add_argument("--huesos")
    for v in VIEWS:
        ap.add_argument("--" + v)
    a = ap.parse_args()

    given = {v: getattr(a, v) for v in VIEWS if getattr(a, v)}
    if "frente" not in given or not ({"izquierda", "derecha"} & set(given)):
        raise SystemExit("Hacen falta al menos la vista de frente y una lateral.")
    target_h = a.alto / CELL_M * CELL_PX
    images, boxes = {}, {}
    for v, path in given.items():
        images[v] = remove_background(Image.open(path), a.tolerancia)
        boxes[v] = bbox(images[v])

    # misma escala real en todas las vistas: las de alzado por la altura, las de planta por el ancho de la vista de frente
    front_w = (boxes["frente"][2] - boxes["frente"][0]) * target_h / (boxes["frente"][3] - boxes["frente"][1])
    scale = {}
    for v in given:
        x0, y0, x1, y1 = boxes[v]
        scale[v] = front_w / (x1 - x0) if v in ("arriba", "abajo") else target_h / (y1 - y0)

    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    place = {}
    for v, img in images.items():
        x0, y0, x1, y1 = boxes[v]
        w, h = round((x1 - x0) * scale[v]), round((y1 - y0) * scale[v])
        if max(w, h) > CANVAS - 2 * MARGIN:
            raise SystemExit(f"La vista '{v}' mide {w}x{h} px y no cabe en {CANVAS}x{CANVAS}. Con 1 cuadro = 0,05 m el lienzo "
                             f"abarca {CANVAS / CELL_PX * CELL_M:.2f} m: reduce --alto o usa un objeto más pequeño.")
        crop = img.crop((x0, y0, x1, y1)).resize((w, h), Image.LANCZOS)
        ox, oy = (CANVAS - w) // 2, (CANVAS - h) // 2
        canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        canvas.alpha_composite(crop, (ox, oy))
        canvas.save(out / f"{a.nombre}_{v}.png")
        place[v] = (x0, y0, scale[v], ox, oy)

    grids = {v: grid_image() for v in given}
    if a.huesos:
        bones = json.loads(Path(a.huesos).read_text(encoding="utf-8"))["huesos"]
        if len(bones) > len(PALETTE):
            raise SystemExit(f"Máximo {len(PALETTE)} huesos.")
        for b in bones:
            if not (0 <= b["id"] < len(PALETTE)) or (b.get("padre") is not None and not (0 <= b["padre"] < len(PALETTE))):
                raise SystemExit(f"Id de hueso fuera de 0-{len(PALETTE) - 1}: {b}")
            for v, (x0, y0, s, ox, oy) in place.items():
                if v not in b:
                    continue
                cx, cy = (b[v][0] - x0) * s + ox, (b[v][1] - y0) * s + oy
                d = ImageDraw.Draw(grids[v])
                if b.get("padre") is not None:
                    d.ellipse([cx - 11, cy - 11, cx + 11, cy + 11], fill=PALETTE[b["padre"]] + (255,))
                d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=PALETTE[b["id"]] + (255,))
    for v, g in grids.items():
        g.save(out / f"{a.nombre}_{v}_malla.png")
    print(f"Listo: {len(given)} vistas y mallas en {out}")


if __name__ == "__main__":
    main()
