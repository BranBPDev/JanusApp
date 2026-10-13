"""Objetos redondos con salientes (tapas, pestillos, asas...): núcleo elíptico + malla de los salientes.

El contorno de las vistas da el cuerpo (un elipsoide ajustado ignorando los salientes) y lo que sobresale de él es el
casco visual menos ese cuerpo. Las marcas violeta de las mallas (huella del saliente vista de frente) indican qué partes
sobresalen y con qué forma en planta, de modo que el resultado no se rompe en bloques."""
import numpy as np
from PIL import Image

from app.shape.atlas import Atlas
from app.shape.field import compose, grid_shape, make_arrays
from app.shape.mesh_ops import remove_small_components, taubin_smooth
from app.shape.preprocess import fill_holes
from app.shape.qem import decimate
from app.shape.surface_nets import surface_nets

MIN_INLIERS = 0.8        # fracción mínima del contorno que debe encajar en la elipse del cuerpo
MAX_EXTRAS = 0.25        # los salientes no pueden ser más del 25 % del volumen (si no, no es «un cuerpo con salientes»)
AXIS_TOLERANCE = 0.08    # diferencia máxima entre las medidas de un mismo eje en distintas vistas
RESOLUTION = 176         # rejilla de los salientes
GAP = 1.5                # voxels que debe sobresalir algo para considerarse saliente
EMBED = 1.5              # voxels que se hunden los salientes en el cuerpo (para que no queden despegados)
DECIMATE = 0.002        # error máximo al simplificar los salientes (fracción del alto)
ATLAS_CAP = 512

# (eje horizontal, eje vertical) de cada vista en el mundo: 0 = x, 1 = y, 2 = z
_AXES = {"front": (0, 1), "back": (0, 1), "left": (2, 1), "right": (2, 1), "top": (0, 2), "bottom": (0, 2)}


def _boundary(mask):
    inner = mask.copy()
    inner[1:] &= mask[:-1]
    inner[:-1] &= mask[1:]
    inner[:, 1:] &= mask[:, :-1]
    inner[:, :-1] &= mask[:, 1:]
    ys, xs = np.nonzero(mask & ~inner)
    return xs + 0.5, ys + 0.5


def robust_ellipse(mask, tol: float = 0.06, iters: int = 6):
    """Elipse (alineada con los ejes) que mejor encaja en el contorno ignorando lo que sobresale.
    Devuelve (cx, cy, rx, ry, fracción de contorno que encaja) en píxeles de la máscara, o None."""
    x, y = _boundary(mask)
    if len(x) < 24:
        return None
    h, w = mask.shape
    sx, sy = w / 2.0, h / 2.0
    xn, yn = (x - sx) / sx, (y - sy) / sy
    keep = np.ones(len(x), bool)
    params = None
    for _ in range(iters):
        if keep.sum() < 12:
            return None
        X = np.stack([xn[keep] ** 2, yn[keep] ** 2, xn[keep], yn[keep]], 1)
        sol = np.linalg.lstsq(X, np.ones(keep.sum()), rcond=None)[0]
        A, B, C, D = sol
        if A <= 1e-9 or B <= 1e-9:
            return None
        cx, cy = -C / (2 * A), -D / (2 * B)
        F = 1 + C * C / (4 * A) + D * D / (4 * B)
        rx, ry = np.sqrt(F / A), np.sqrt(F / B)
        params = (cx, cy, rx, ry)
        err = np.abs(((xn - cx) / rx) ** 2 + ((yn - cy) / ry) ** 2 - 1)
        new = err < tol
        if (new == keep).all():
            break
        keep = new
    cx, cy, rx, ry = params
    return cx * sx + sx, cy * sy + sy, rx * sx, ry * sy, float(keep.mean())


def fit_core(masks: dict, dims, flips: dict):
    """Cuerpo elíptico del objeto ignorando los salientes. Devuelve None si el contorno no es el de un elipsoide con
    salientes. Resultado: centro y semiejes en unidades del modelo (alto = 1) y el marco de cada vista."""
    ext = {0: dims[0], 1: dims[1], 2: dims[2]}
    est = {0: [], 1: [], 2: []}      # semiejes por eje del mundo
    cen = {0: [], 1: [], 2: []}      # centro por eje del mundo (desde el borde inferior/izquierdo del casco)
    frames, inliers = {}, []
    for key, mask in masks.items():
        e = robust_ellipse(mask)
        if e is None:
            return None
        cx, cy, rx, ry, frac = e
        h, w = mask.shape
        inliers.append(frac)
        frames[key] = (cx / w, cy / h, rx / w, ry / h)
        ah, av = _AXES[key]
        fh, fv = ext[ah] / w, ext[av] / h
        est[ah].append(rx * fh)
        est[av].append(ry * fv)
        # centro como distancia desde el origen del casco, en el eje del mundo de cada lado de la imagen
        if key == "front":
            cen[0].append(cx * fh)
            cen[1].append((h - cy) * fv)
        elif key == "back":
            cen[0].append((w - cx) * fh)
            cen[1].append((h - cy) * fv)
        elif key == "right":
            cen[2].append((w - cx) * fh if flips.get("fr") else cx * fh)
            cen[1].append((h - cy) * fv)
        elif key == "left":
            cen[2].append(cx * fh if flips.get("fl") else (w - cx) * fh)
            cen[1].append((h - cy) * fv)
        elif key == "top":
            cen[0].append(cx * fh)
            cen[2].append((h - cy) * fv if flips.get("ft") else cy * fv)
        else:
            cen[0].append(cx * fh)
            cen[2].append(cy * fv if flips.get("fb") else (h - cy) * fv)
    if min(inliers) < MIN_INLIERS or any(not est[a] for a in range(3)):
        return None
    semi = [float(np.mean(est[a])) for a in range(3)]
    for a in range(3):
        if len(est[a]) > 1 and (max(est[a]) - min(est[a])) / max(est[a]) > AXIS_TOLERANCE:
            return None
    lo = np.array([-dims[0] / 2, 0.0, -dims[2] / 2])
    center = np.array([float(np.mean(cen[a])) for a in range(3)]) + lo
    return {"center": center, "semi": np.array(semi), "frames": frames, "inliers": float(np.mean(inliers))}


def footprints(overlays: dict, views: dict) -> dict:
    """Huellas de los salientes: máscaras (recortadas y reescaladas a la silueta de cada vista) de las marcas violeta,
    con el interior relleno."""
    out = {}
    for key, raw in overlays.items():
        if raw is None or key not in views or not raw.any():
            continue
        v = views[key]
        x0, y0, x1, y1 = [int(round(c * v.scale)) for c in v.box]
        crop = raw[y0:y1, x0:x1]
        if not crop.any():
            continue
        img = Image.fromarray(crop.astype(np.uint8) * 255, "L").resize((v.mask.shape[1], v.mask.shape[0]), Image.NEAREST)
        out[key] = fill_holes(np.asarray(img) > 127)
    return out


def _dilate(vol, n):
    for _ in range(n):
        g = vol.copy()
        g[1:] |= vol[:-1]; g[:-1] |= vol[1:]
        g[:, 1:] |= vol[:, :-1]; g[:, :-1] |= vol[:, 1:]
        g[:, :, 1:] |= vol[:, :, :-1]; g[:, :, :-1] |= vol[:, :, 1:]
        vol = g
    return vol


def _erode(vol, n):
    return ~_dilate(~vol, n)


def build_extras(masks, images, fp_masks, dims, flips, core, progress=None):
    """Malla de lo que sobresale del cuerpo. Devuelve {'V','F','uv','texture'} o None si no hay salientes.
    V en el mismo espacio del modelo (alto = 1, apoyado en y = 0, centrado en x/z); 'uv' (n_caras,3,2) normalizadas
    sobre 'texture' (atlas de las vistas)."""
    shape, _ = grid_shape(dims, RESOLUTION)
    arrays = make_arrays(masks, shape)
    hull, _ = compose(arrays, shape, **flips)
    hull = hull > 0.5
    nx, ny, nz = shape
    lo = np.array([-dims[0] / 2, 0.0, -dims[2] / 2])
    cell = np.array(dims, np.float64) / np.array(shape)
    xs = lo[0] + (np.arange(nx) + 0.5) * cell[0]
    ys = lo[1] + (np.arange(ny) + 0.5) * cell[1]
    zs = lo[2] + (np.arange(nz) + 0.5) * cell[2]
    c, a = core["center"], core["semi"]
    q = np.sqrt(((xs[:, None, None] - c[0]) / a[0]) ** 2 + ((ys[None, :, None] - c[1]) / a[1]) ** 2 +
                ((zs[None, None, :] - c[2]) / a[2]) ** 2)

    vox = float(cell.max())
    out = hull & (q > 1.0 + GAP * vox / float(a.min()))
    if fp_masks:                                    # solo lo marcado como saliente (unión de las huellas)
        arr = make_arrays(fp_masks, shape)
        union = np.zeros(shape, bool)
        for key, arr_k in arr.items():
            vol, _ = compose({key: arr_k}, shape, **flips)
            union |= vol > 0.5
        out &= union
    out = _dilate(_erode(out, 1), 1)                # quita cáscaras de un voxel
    n_out = int(out.sum())
    if n_out < 30 or n_out > MAX_EXTRAS * hull.sum():
        return None

    # los salientes se prolongan hacia dentro del cuerpo (en radial) para quedar bien unidos
    idx = np.argwhere(out)
    pos = np.stack([xs[idx[:, 0]], ys[idx[:, 1]], zs[idx[:, 2]]], 1)
    grad = (pos - c) / a ** 2
    grad /= np.maximum(np.linalg.norm(grad, axis=1, keepdims=True), 1e-12)
    solid = out.copy()
    steps = int(np.ceil(GAP + EMBED))
    for s in range(1, steps + 1):
        p = pos - grad * s * vox
        i = np.clip(np.floor((p[:, 0] - lo[0]) / cell[0]).astype(int), 0, nx - 1)
        j = np.clip(np.floor((p[:, 1] - lo[1]) / cell[1]).astype(int), 0, ny - 1)
        k = np.clip(np.floor((p[:, 2] - lo[2]) / cell[2]).astype(int), 0, nz - 1)
        solid[i, j, k] = True

    pad = 2
    V, F = surface_nets(np.pad(solid.astype(np.float32), pad))
    if len(F) == 0:
        return None
    V, F = remove_small_components(V, F)
    V = (V - pad + 0.5) * cell + lo
    V = taubin_smooth(V, F, 4)
    V, F = decimate(V, F, DECIMATE, 12)

    box_lo = lo
    atlas = Atlas(images, masks, (box_lo, box_lo + np.array(dims, np.float64)), flips, cap=ATLAS_CAP)
    uv = atlas.corner_uvs(V, F, np.zeros(len(F), int), (0.0, 0.0))
    return {"V": V.astype(np.float64), "F": F.astype(np.int32), "uv": uv, "texture": atlas.texture}


def assign_sides(V, F, opening):
    """True para las caras que van con la parte móvil: las del lado al que apunta el corte y todo lo que cae dentro
    del círculo del botón (el cierre viaja entero con la tapa)."""
    centroid = V[F].mean(axis=1)
    moving = (centroid - np.asarray(opening["point"])) @ np.asarray(opening["normal"]) > 0
    btn = opening.get("button")
    if btn:
        cx, cy = btn["center"]
        near = np.hypot(centroid[:, 0] - cx, centroid[:, 1] - cy) < 1.1 * btn["radius"]
        moving |= near & (centroid[:, 2] > 0)
    return moving
