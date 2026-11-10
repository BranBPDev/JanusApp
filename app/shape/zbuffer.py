"""Rasterizador por software con z-buffer (numpy, sin Qt): visibilidad exacta por píxel, normales y UV interpoladas."""
import numpy as np

_MAX_FRAGMENTS = 1_000_000


def _bary(P, px, py):
    """Coordenadas baricéntricas (l0,l1,l2) de los puntos (px,py) respecto a triángulos P (...,3,2); px,py con la misma forma que P[...,0,0]."""
    x0, y0, x1, y1, x2, y2 = P[..., 0, 0], P[..., 0, 1], P[..., 1, 0], P[..., 1, 1], P[..., 2, 0], P[..., 2, 1]
    det = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    det = np.where(np.abs(det) < 1e-12, 1e-12, det)
    l0 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / det
    l1 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / det
    return l0, l1, 1.0 - l0 - l1


def fragments(P, Z, width, height):
    """Genera por lotes los fragmentos (píxel, profundidad, triángulo) de los triángulos P (k,3,2) con profundidades Z (k,3)."""
    k = len(P)
    if k == 0:
        return
    mn, mx = P.min(axis=1), P.max(axis=1)
    x0 = np.maximum(np.ceil(mn[:, 0] - 0.5), 0).astype(np.int64)
    x1 = np.minimum(np.floor(mx[:, 0] - 0.5), width - 1).astype(np.int64)
    y0 = np.maximum(np.ceil(mn[:, 1] - 0.5), 0).astype(np.int64)
    y1 = np.minimum(np.floor(mx[:, 1] - 0.5), height - 1).astype(np.int64)
    ok = np.nonzero((x1 >= x0) & (y1 >= y0))[0]
    if not len(ok):
        return
    bw, bh = x1[ok] - x0[ok] + 1, y1[ok] - y0[ok] + 1
    ok = ok[np.argsort(bw * bh, kind="stable")]
    bw, bh = x1[ok] - x0[ok] + 1, y1[ok] - y0[ok] + 1
    x0f, y0f, x1f, y1f, x2f, y2f = (P[:, v, c].astype(np.float64) for v in range(3) for c in range(2))
    det = (y1f - y2f) * (x0f - x2f) + (x2f - x1f) * (y0f - y2f)
    det = np.where(np.abs(det) < 1e-12, 1e-12, det)
    a0, b0 = (y1f - y2f) / det, (x2f - x1f) / det
    a1, b1 = (y2f - y0f) / det, (x0f - x2f) / det
    c0, c1 = -(a0 * x2f + b0 * y2f), -(a1 * x2f + b1 * y2f)
    # z = l0*z0 + l1*z1 + (1-l0-l1)*z2 = za*x + zb*y + zc
    z0, z1, z2 = Z[:, 0], Z[:, 1], Z[:, 2]
    za, zb = a0 * (z0 - z2) + a1 * (z1 - z2), b0 * (z0 - z2) + b1 * (z1 - z2)
    zc = c0 * (z0 - z2) + c1 * (z1 - z2) + z2
    coef = (a0, b0, c0, a1, b1, c1, za, zb, zc)
    i = 0
    while i < len(ok):
        j = min(len(ok), i + 8192)
        while True:
            mw, mh = int(bw[i:j].max()), int(bh[i:j].max())
            if (j - i) * mw * mh <= _MAX_FRAGMENTS or j - i == 1:
                break
            j = i + max(1, (j - i) // 2)
        t = ok[i:j]
        gxp = (x0[t][:, None] + np.arange(mw)[None, :] + 0.5)               # (n, mw) centros de píxel
        gyp = (y0[t][:, None] + np.arange(mh)[None, :] + 0.5)               # (n, mh)
        A0, B0, C0, A1, B1, C1, ZA, ZB, ZC = (c[t][:, None] for c in coef)
        l0 = (A0 * gxp)[:, None, :] + (B0 * gyp + C0)[:, :, None]           # los planos son lineales: suma de un término por columna y otro por fila
        l1 = (A1 * gxp)[:, None, :] + (B1 * gyp + C1)[:, :, None]
        l2 = 1.0 - l0 - l1
        e = -1e-6
        inside = (l0 >= e) & (l1 >= e) & (l2 >= e)
        inside &= (np.arange(mw)[None, None, :] < bw[i:j][:, None, None]) & (np.arange(mh)[None, :, None] < bh[i:j][:, None, None])
        ti, yi, xi = np.nonzero(inside)
        z = (ZA * gxp)[ti, xi] + (ZB * gyp + ZC)[ti, yi]
        gy = (y0[t][:, None] + np.arange(mh)[None, :])[:, :, None]
        gx = (x0[t][:, None] + np.arange(mw)[None, :])[:, None, :]
        yield (gy[ti, yi, 0] * width + gx[ti, 0, xi]), z, t[ti]
        i = j


def visibility(P, Z, width, height, abort=None):
    """Triángulo más cercano (mayor Z) de cada píxel: devuelve (zbuf (h*w), idbuf (h*w) con -1 donde no hay nada).
    abort: función opcional; si devuelve True se deja el cálculo a medias."""
    zbuf = np.full(width * height, -np.inf)
    idbuf = np.full(width * height, -1, np.int64)
    for pix, z, tri in fragments(P, Z, width, height):
        if abort is not None and abort():
            break
        o = np.lexsort((z, pix))
        pix, z, tri = pix[o], z[o], tri[o]
        last = np.ones(len(pix), bool)
        last[:-1] = pix[1:] != pix[:-1]
        pix, z, tri = pix[last], z[last], tri[last]
        better = z > zbuf[pix]
        zbuf[pix[better]] = z[better]
        idbuf[pix[better]] = tri[better]
    return zbuf, idbuf


def sample(tex, u, v):
    """Muestreo bilineal de la textura (h,w,4) en coordenadas de píxel (u,v); devuelve (n,4) float 0-255."""
    h, w = tex.shape[:2]
    u, v = u - 0.5, v - 0.5
    u0, v0 = np.floor(u).astype(np.int64), np.floor(v).astype(np.int64)
    fu, fv = (u - u0)[:, None], (v - v0)[:, None]
    xa, xb = np.clip(u0, 0, w - 1), np.clip(u0 + 1, 0, w - 1)
    ya, yb = np.clip(v0, 0, h - 1), np.clip(v0 + 1, 0, h - 1)
    t = tex.astype(np.float32)
    return (t[ya, xa] * (1 - fu) * (1 - fv) + t[ya, xb] * fu * (1 - fv) + t[yb, xa] * (1 - fu) * fv + t[yb, xb] * fu * fv)


def shade(P, tri, pix, width, face_n, face_uv, base_color, tex, light):
    """Color (n,3) y alfa (n,) de los píxeles 'pix' cubiertos por los triángulos 'tri'."""
    px, py = (pix % width) + 0.5, (pix // width) + 0.5
    l0, l1, l2 = _bary(P[tri], px, py)
    L = np.stack([l0, l1, l2], axis=1)                                  # (n,3)
    n = (face_n[tri] * L[:, :, None]).sum(axis=1)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    lum = 0.4 + 0.6 * np.clip(n @ light, 0, 1)
    if face_uv is not None and tex is not None:
        uv = (face_uv[tri] * L[:, :, None]).sum(axis=1)
        c = sample(tex, uv[:, 0], uv[:, 1])
        col, alpha = c[:, :3], c[:, 3] / 255.0
    else:
        col, alpha = base_color[tri], np.ones(len(tri))
    return np.clip(col * lum[:, None], 0, 255), alpha
