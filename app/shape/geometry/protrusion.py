"""Objetos redondos con salientes (tapas, pestillos, asas...): núcleo elíptico + malla de los salientes.

El contorno de las vistas da el cuerpo (un elipsoide ajustado ignorando los salientes) y lo que sobresale de él es el
casco visual menos ese cuerpo. Las huellas de salientes del JSON (forma del saliente en una vista) indican qué partes
sobresalen y con qué forma en planta, de modo que el resultado no se rompe en bloques."""
import numpy as np

from app.shape.geometry.coords import VIEW_AXES
from app.shape.geometry.field import compose, grid_shape, make_arrays
from app.shape.geometry.mesh_ops import remove_small_components, taubin_smooth
from app.shape.geometry.qem import decimate
from app.shape.geometry.surface_nets import surface_nets
from app.shape.texture.atlas import Atlas

MIN_INLIERS = 0.8        # fracción mínima del contorno que debe encajar en la elipse del cuerpo
MAX_EXTRAS = 0.25        # los salientes no pueden ser más del 25 % del volumen (si no, no es «un cuerpo con salientes»)
AXIS_TOLERANCE = 0.08    # diferencia máxima entre las medidas de un mismo eje en distintas vistas
COARSE = 96              # rejilla gruesa para localizar los salientes
RESOLUTION = 360         # rejilla fina de cada saliente (sólo en su caja)
SMOOTH = 3               # pasadas de suavizado
GAP = 2.0                # voxels que debe sobresalir algo para considerarse saliente
EMBED = 4.0              # voxels que se hunden los salientes en el cuerpo (para que no queden despegados)
DECIMATE = 0.002        # error máximo al simplificar los salientes (fracción del alto)
ATLAS_CAP = 512


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
        ah, av = VIEW_AXES[key]
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


def _targets(arrays, flips):
    """Siluetas proyectadas en ejes del mundo: lista de (array 2D, eje de proyección). Misma convención que compose()."""
    t = []
    if "front" in arrays:
        t.append((arrays["front"][::-1].T, 2))
    if "back" in arrays:
        t.append((arrays["back"][::-1, ::-1].T, 2))
    if "right" in arrays:
        r = arrays["right"][::-1]
        t.append((r[:, ::-1] if flips.get("fr") else r, 0))
    if "left" in arrays:
        l = arrays["left"][::-1, ::-1]
        t.append((l[:, ::-1] if flips.get("fl") else l, 0))
    if "top" in arrays:
        a = arrays["top"]
        t.append(((a[::-1] if flips.get("ft") else a).T, 1))
    if "bottom" in arrays:
        a = arrays["bottom"]
        t.append(((a if flips.get("fb") else a[::-1]).T, 1))
    return t


def _local(targets, box):
    """Volumen (bool) de la intersección de siluetas extruidas dentro de la caja de índices (i0,i1,j0,j1,k0,k1)."""
    i0, i1, j0, j1, k0, k1 = box
    vol = np.ones((i1 - i0, j1 - j0, k1 - k0), bool)
    for t, axis in targets:
        if axis == 2:
            vol &= (t[i0:i1, j0:j1] > 0.5)[:, :, None]
        elif axis == 0:
            vol &= (t[j0:j1, k0:k1] > 0.5)[None, :, :]
        else:
            vol &= (t[i0:i1, k0:k1] > 0.5)[:, None, :]
    return vol


def _components(mask, limit=12):
    comps, rest = [], mask.copy()
    while rest.any() and len(comps) < limit:
        seed = np.zeros(mask.shape, bool)
        seed[tuple(np.argwhere(rest)[0])] = True
        for _ in range(400):
            grown = _dilate(seed, 1) & rest
            if (grown == seed).all():
                break
            seed = grown
        comps.append(seed)
        rest &= ~seed
    return comps


def build_extras(masks, images, fp_masks, dims, flips, core, progress=None):
    """Malla de lo que sobresale del cuerpo. Devuelve {'V','F','uv','texture'} o None si no hay salientes.
    V en el mismo espacio del modelo (alto = 1, apoyado en y = 0, centrado en x/z); 'uv' (n_caras,3,2) normalizadas
    sobre 'texture' (atlas de las vistas). Cada saliente se vuelve a muestrear con una rejilla fina sólo en su caja."""
    lo = np.array([-dims[0] / 2, 0.0, -dims[2] / 2])
    c, a = core["center"], core["semi"]

    def inside_core(xs, ys, zs):
        return np.sqrt(((xs[:, None, None] - c[0]) / a[0]) ** 2 + ((ys[None, :, None] - c[1]) / a[1]) ** 2 +
                       ((zs[None, None, :] - c[2]) / a[2]) ** 2)

    # 1) pasada gruesa: dónde hay salientes
    shape, _ = grid_shape(dims, COARSE)
    hull, _ = compose(make_arrays(masks, shape), shape, **flips)
    cell = np.array(dims, np.float64) / np.array(shape)
    axes = [lo[i] + (np.arange(shape[i]) + 0.5) * cell[i] for i in range(3)]
    q = inside_core(*axes)
    out = (hull > 0.5) & (q > 1.0 + GAP * float(cell.max()) / float(a.min()))
    if fp_masks:
        arr = make_arrays(fp_masks, shape)
        union = np.zeros(shape, bool)
        for key, arr_k in arr.items():
            vol, _ = compose({key: arr_k}, shape, **flips)
            union |= vol > 0.5
        out &= union
    out = _dilate(_erode(out, 1), 1)
    if out.sum() < 4 or out.sum() > MAX_EXTRAS * (hull > 0.5).sum():
        return None
    comps = _components(_dilate(out, 1) & (hull > 0.5))

    # 2) pasada fina por saliente
    fshape, _ = grid_shape(dims, RESOLUTION)
    fcell = np.array(dims, np.float64) / np.array(fshape)
    fine_targets = _targets(make_arrays(masks, fshape), flips)
    fp_targets = [_targets({k: v}, flips)[0] for k, v in make_arrays(fp_masks, fshape).items()] if fp_masks else []
    fvox = float(fcell.max())
    meshes = []
    for comp in comps:
        idx = np.argwhere(comp)
        wlo = lo + (idx.min(0) - 2) * cell
        whi = lo + (idx.max(0) + 3) * cell
        margin = (GAP + EMBED + 4) * fcell
        i_lo = np.clip(np.floor((wlo - margin - lo) / fcell).astype(int), 0, np.array(fshape) - 1)
        i_hi = np.clip(np.ceil((whi + margin - lo) / fcell).astype(int), 1, np.array(fshape))
        box = (i_lo[0], i_hi[0], i_lo[1], i_hi[1], i_lo[2], i_hi[2])
        lshape = tuple(i_hi - i_lo)
        blo = lo + i_lo * fcell
        laxes = [blo[i] + (np.arange(lshape[i]) + 0.5) * fcell[i] for i in range(3)]
        ql = inside_core(*laxes)
        sel = _local(fine_targets, box) & (ql > 1.0 + GAP * fvox / float(a.min()))
        if fp_targets:
            un = np.zeros(lshape, bool)
            for t, axis in fp_targets:
                un |= _local([(t, axis)], box)
            sel &= un
        sel = _dilate(_erode(sel, 1), 1)
        if sel.sum() < 200:
            continue
        idx = np.argwhere(sel)
        pos = np.stack([laxes[0][idx[:, 0]], laxes[1][idx[:, 1]], laxes[2][idx[:, 2]]], 1)
        grad = (pos - c) / a ** 2
        grad /= np.maximum(np.linalg.norm(grad, axis=1, keepdims=True), 1e-12)
        solid = sel.copy()
        for s in range(1, int(np.ceil(GAP + EMBED)) + 1):
            p = pos - grad * s * fvox
            i = np.clip(np.floor((p[:, 0] - blo[0]) / fcell[0]).astype(int), 0, lshape[0] - 1)
            j = np.clip(np.floor((p[:, 1] - blo[1]) / fcell[1]).astype(int), 0, lshape[1] - 1)
            k = np.clip(np.floor((p[:, 2] - blo[2]) / fcell[2]).astype(int), 0, lshape[2] - 1)
            solid[i, j, k] = True
        pad = 2
        V, F = surface_nets(np.pad(solid.astype(np.float32), pad))
        if len(F) == 0:
            continue
        V, F = remove_small_components(V, F)
        V = (V - pad + 0.5) * fcell + blo
        V = taubin_smooth(V, F, SMOOTH)
        V, F = decimate(V, F, DECIMATE, 12)
        meshes.append((V, F))
    if not meshes:
        return None
    V = np.concatenate([m[0] for m in meshes])
    offs = np.cumsum([0] + [len(m[0]) for m in meshes])
    F = np.concatenate([m[1] + o for m, o in zip(meshes, offs)])

    atlas = Atlas(images, masks, (lo, lo + np.array(dims, np.float64)), flips, cap=ATLAS_CAP)
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
