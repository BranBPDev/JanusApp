"""Lo que «ve» la IA: un informe de texto del objeto (medidas, colores, siluetas, relieves, avisos) y comprobaciones de lo pedido."""
import re

import numpy as np

from app.shape.spec.blueprint import build_blueprint
from app.shape.spec.schema import VIEW_KEYS, ObjectSpec, SpecError

_NAMES = {"front": "frente", "back": "detrás", "left": "izquierda", "right": "derecha", "top": "arriba", "bottom": "abajo"}


def build(data: dict):
    """(spec, blueprint) o SpecError con un mensaje legible."""
    try:
        spec = ObjectSpec(data)
        return spec, build_blueprint(spec)
    except SpecError:
        raise
    except Exception as e:
        raise SpecError(f"No se pudo calcular el objeto: {e}")


def _ascii(mask, cols=24, rows=10):
    h, w = mask.shape
    ys, xs = np.linspace(0, h, rows + 1).astype(int), np.linspace(0, w, cols + 1).astype(int)
    out = []
    for r in range(rows):
        line = ""
        for c in range(cols):
            v = mask[ys[r]:max(ys[r + 1], ys[r] + 1), xs[c]:max(xs[c + 1], xs[c] + 1)].mean()
            line += "#" if v > 0.6 else ("+" if v > 0.2 else ".")
        out.append(line)
    return "\n".join(out)


def _colors(view, n=4):
    px = view.rgba[view.mask][:, :3]
    if not len(px):
        return []
    q = (px // 32).astype(np.int32)
    key = q[:, 0] * 64 + q[:, 1] * 8 + q[:, 2]
    vals, counts = np.unique(key, return_counts=True)
    res = []
    for i in np.argsort(-counts)[:n]:
        sel = px[key == vals[i]].mean(0).astype(int)
        res.append(f"#{sel[0]:02x}{sel[1]:02x}{sel[2]:02x} {counts[i] * 100 // len(px)}%")
    return res


def brief(data: dict) -> str:
    """Resumen corto del objeto para el prompt (no calcula el modelo)."""
    if not data:
        return "No hay objeto todavía."
    m = data.get("medidas_m", {})
    tex = ", ".join(f"{k}={v['color']}" if "color" in v else f"{k}=(degradado)" for k, v in (data.get("texturas") or {}).items()
                    if not k.startswith("a_"))
    rel = "; ".join(f"{r.get('tipo')}({r.get('textura')})" for r in data.get("relieves") or []) or "ninguno"
    return (f"nombre={data.get('nombre')} medidas={m.get('ancho')}x{m.get('alto')}x{m.get('fondo')} m\n"
            f"texturas: {tex}\nrelieves: {rel}\ninterior: {'sí' if data.get('interior') else 'no'}")


def report(data: dict) -> str:
    """Informe completo (lo que se enseña al usuario y sirve para verificar)."""
    spec, bp = build(data)
    lines = [f"Objeto «{spec.name}»: {spec.width:g} × {spec.height:g} × {spec.depth:g} m (ancho × alto × fondo)."]
    lines.append("Texturas: " + ", ".join(f"{k}" + (f" {data['texturas'][k]['color']}" if "color" in data["texturas"][k] else "") for k in data.get("texturas", {})
                                            if not k.startswith("a_")))
    for k, v in bp.views.items():
        ys, xs = np.nonzero(v.mask)
        lines.append(f"Vista {_NAMES[k]}: silueta {np.ptp(xs) + 1}×{np.ptp(ys) + 1} px, ocupa {v.mask.mean() * 100:.0f}% del cuadro; colores {', '.join(_colors(v, 3))}.")
    lines.append("Silueta de frente:\n" + _ascii(bp.views["front"].mask))
    if bp.reliefs:
        for r in spec.reliefs:
            lines.append(f"Relieve {r['tipo']} ({r['textura']}).")
    lines.append(f"Se abre por un corte: {'sí' if (data.get('marcas') or {}).get('corte') else 'no'}; interior: {'sí' if bp.interiors else 'no'}.")
    lines += [f"AVISO: {w}" for w in bp.warnings]
    return "\n".join(lines)


def _numbers(node, out):
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        out.append(float(node))
    elif isinstance(node, dict):
        for v in node.values():
            _numbers(v, out)
    elif isinstance(node, list):
        for v in node:
            _numbers(v, out)


def check_request(text: str, data: dict) -> list:
    """Comprobaciones automáticas de que el resultado contiene lo que se pidió (colores #hex y medidas con unidad)."""
    problems = []
    flat = str(data.get("texturas", {})).lower()
    for h in dict.fromkeys(re.findall(r"#[0-9a-fA-F]{6}\b", text)):
        if h.lower() not in flat:
            problems.append(f"Pediste el color {h} y no aparece en las texturas.")
    nums = []
    _numbers({k: v for k, v in data.items() if k not in ("texturas", "interior")}, nums)
    for val, unit in re.findall(r"(\d+(?:[.,]\d+)?)\s*(mm|cm|m)\b", text.lower()):
        v = float(val.replace(",", ".")) * {"mm": 0.001, "cm": 0.01, "m": 1.0}[unit]
        # medidas del objeto (con tolerancia por el margen que añaden los relieves) o cualquier valor del JSON
        if not any(abs(n - v) <= max(0.012 * v, 1e-4) for n in nums):
            m = data.get("medidas_m", {})
            if not any(abs(float(m.get(k, 0)) - v) <= 0.15 * v for k in m):
                problems.append(f"Pediste {val} {unit} ({v:g} m) y no encuentro esa medida en el objeto.")
    return problems
