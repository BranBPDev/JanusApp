"""Ejecuta el programa que escribe la IA (nuevo, color, banda, adorno…) sobre el JSON del objeto con las piezas de la aplicación."""
import copy

from app.ai.assistant import ejemplos, ops
from app.shape.spec.schema import SpecError

SHADES = {"": 1.0, "_claro": None, "_oscuro": None}
BASE = {"rojo": "#d32f2f", "azul": "#1e63d6", "verde": "#2e9e4f", "amarillo": "#f4d51f", "naranja": "#f28c1b", "morado": "#7b3fb5",
        "rosa": "#f28ab4", "negro": "#1b1b1f", "blanco": "#f4f4f4", "gris": "#8d8f98", "marron": "#7a4a26", "dorado": "#d9a928",
        "plateado": "#c4c8d0", "turquesa": "#22c7c7", "beige": "#e6d5b0"}
FIXED = {"negro_claro": "#4a4a52", "negro_oscuro": "#0b0b0d", "blanco_oscuro": "#cfcfcf", "blanco_claro": "#ffffff"}
ORNAMENTS = {"triskel", "pinchos", "adorno"}
SLOT_TEXTURE = {"tapa": "tapa", "fondo": "fondo", "banda": "banda", "boton": "cierre", "cuerda": "cuerda", "cadena": "cadena",
                "triskel": "triskel", "pinchos": "pinchos", "adorno": "adorno"}
FORMS = {"triskel", "pinchos", "anillo", "bola", "cono", "cilindro"}


def color_hex(name: str, hexes) -> str:
    if name.startswith("<h"):
        i = int(name[2:-1])
        if i >= len(hexes):
            raise SpecError(f"El programa usa un color #{i + 1} que no existe.")
        return hexes[i]
    if name in FIXED:
        return FIXED[name]
    base, _, shade = name.partition("_")
    if base not in BASE:
        raise SpecError(f"Color desconocido «{name}».")
    r, g, b = (int(BASE[base][i:i + 2], 16) for i in (1, 3, 5))
    if shade == "claro":
        r, g, b = (round(c + (255 - c) * 0.45) for c in (r, g, b))
    elif shade == "oscuro":
        r, g, b = (round(c * 0.55) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def state(spec) -> list:
    """Fichas que describen el objeto actual (la IA las lee como contexto)."""
    if not spec:
        return ["vacio"]
    tex = spec.get("texturas", {})
    out = ["esfera_banda" if "tapa" in tex else "esfera_simple"]
    if any(c.get("textura") == "banda" for v in spec.get("vistas", {}).values() for c in v.get("capas", [])):
        out.append("tiene_banda")
    rel = spec.get("relieves", [])
    kinds = {r.get("tipo") for r in rel}
    names = {r.get("textura") for r in rel}
    if "cuerda" in kinds:
        out.append("tiene_cuerda")
    if "cadena" in kinds:
        out.append("tiene_cadena")
    if "triskel" in names or "triskel" in tex:
        out.append("tiene_triskel")
    if "pinchos" in names:
        out.append("tiene_pinchos")
    if "adorno" in names:
        out.append("tiene_adorno")
    layers = [c for v in spec.get("vistas", {}).values() for c in v.get("capas", []) if c.get("textura") == "triskel"]
    if layers:
        out.append("triskel_plano")
        if any("tallado" in c for c in layers):
            out.append("tiene_tallado")
    return out


def _num(tok, nums, where):
    if tok.startswith("<n") and tok.endswith(">") and tok[2:-1].isdigit() and int(tok[2:-1]) < len(nums):
        return nums[int(tok[2:-1])]
    raise SpecError(f"{where}: falta la medida.")


def _slots(data, slot):
    tex = data.get("texturas", {})
    if slot in ("todo", "cuerpo"):
        return ["cuerpo"] if "cuerpo" in tex else [t for t in ("tapa", "fondo") if t in tex]
    if slot in ("tapa", "fondo", "boton") and "cuerpo" in tex:
        raise SpecError("Este objeto es de un solo color; pídelo «con banda» para poder colorear arriba y abajo por separado.")
    name = SLOT_TEXTURE.get(slot)
    if name == "banda" and name not in tex:
        name = next((n for n in ("cuerda", "cadena") if n in tex), name)
    if name not in tex:
        raise SpecError(f"El objeto no tiene «{slot}».")
    return [name]


def run(spec, prog, hexes=(), nums=()):
    """(spec_nuevo, cambios). Lanza SpecError si el programa no se puede aplicar."""
    data = copy.deepcopy(spec) if spec else {}
    log, i = [], 0
    toks = [t for t in prog if t != "fin"]
    for k in range(len(toks) - 1):                      # «plano adorno triskel» -> «adorno triskel plano»
        if toks[k] in ("plano", "relieve") and toks[k + 1] == "adorno":
            toks[k], toks[k + 1] = "adorno", toks[k]
            if k + 2 < len(toks):
                toks[k + 1], toks[k + 2] = toks[k + 2], toks[k + 1]

    def take(*allowed):
        nonlocal i
        if i < len(toks) and (not allowed or toks[i] in allowed):
            i += 1
            return toks[i - 1]
        return None

    def is_color(t):
        return t is not None and (t.startswith("<h") or t.split("_")[0] in BASE or t in FIXED)

    def optional_color():
        nonlocal i
        if i < len(toks) and is_color(toks[i]):
            i += 1
            return color_hex(toks[i - 1], hexes)
        return None

    while i < len(toks):
        op = toks[i]
        i += 1
        if op != "nuevo" and not data:
            raise SpecError("Todavía no hay ningún objeto: pídeme primero uno («hazme una esfera con banda y botón»).")
        if op == "nuevo":
            kind = take("simple", "banda")
            if not kind:
                raise SpecError("«nuevo» necesita simple o banda.")
            data = ejemplos.ejemplo("esfera_banda_boton" if kind == "banda" else "esfera_simple")
            log.append("objeto nuevo " + ("con banda y botón" if kind == "banda" else "simple"))
        elif op == "diam":
            d = _num(toks[i] if i < len(toks) else "", nums, "diam")
            i += 1
            if not data:
                raise SpecError("No hay objeto al que cambiar el tamaño.")
            if not 0.02 <= d <= 3:
                raise SpecError("El diámetro debe estar entre 2 cm y 3 m.")
            data, _ = ops.apply_ops(data, [{"op": "escalar", "factor": d / (2 * ops.radius(data))}])
            log.append(f"diámetro {d * 100:g} cm")
        elif op == "escalar":
            k = take()
            if not k or not k.startswith("x"):
                raise SpecError("«escalar» necesita un factor.")
            data, _ = ops.apply_ops(data, [{"op": "escalar", "factor": float(k[1:])}])
            log.append(f"tamaño ×{k[1:]}")
        elif op == "color":
            slot, col = take(), take()
            if not data:
                raise SpecError("No hay objeto que colorear.")
            if slot is None or not is_color(col):
                raise SpecError("«color» necesita una zona y un color.")
            hx = color_hex(col, hexes)
            for tex in _slots(data, slot):
                data, _ = ops.apply_ops(data, [{"op": "color", "textura": tex, "valor": hx}])
            log.append(f"{slot} → {hx}")
        elif op == "banda":
            kind = take("cuerda", "cadena")
            if not kind:
                raise SpecError("«banda» necesita cuerda o cadena.")
            col = optional_color()
            log.append(ops.band_by(data, kind, col))
        elif op in ("a_cuerda", "a_cadena"):
            dst = op[2:]
            log.append(ops.convert_reliefs(data, "cadena" if dst == "cuerda" else "cuerda", dst, optional_color()))
        elif op == "adorno":
            form = take(*FORMS)
            if not form:
                raise SpecError("«adorno» necesita una forma.")
            col, size, count, flat, carve = None, None, None, False, None
            while i < len(toks):
                if toks[i] in ("tallado", "tallado_relieve"):
                    carve = {"tipo": "relieve" if toks[i] == "tallado_relieve" else "grabado", "profundidad": 0.8}
                    i += 1
                elif toks[i] in ("piedra", "madera"):
                    carve = carve or {"tipo": "grabado", "profundidad": 0.8}
                    carve["grano"] = toks[i]
                    i += 1
                elif toks[i] in ("plano", "relieve"):
                    flat = toks[i] == "plano"
                    i += 1
                elif is_color(toks[i]):
                    col = optional_color()
                elif toks[i] == "tam":
                    i += 1
                    size = _num(toks[i] if i < len(toks) else "", nums, "tam")
                    i += 1
                elif toks[i] == "cant" and i + 1 < len(toks) and toks[i + 1].isdigit():
                    count = int(toks[i + 1])
                    i += 2
                else:
                    break
            if not data:
                raise SpecError("No hay objeto al que añadir el adorno.")
            if col is None and form == "triskel":
                col = (data.get("texturas", {}).get("cuerda") or data.get("texturas", {}).get("cadena") or {}).get("color")
            log.append(ops.add_ornament(data, form, col, size, count, flat=flat and form == "triskel", carve=carve if form == "triskel" else None))
        elif op == "tallar":
            what = take("triskel")
            if not what:
                raise SpecError("«tallar» necesita qué tallar (triskel).")
            carve = {"tipo": "grabado", "profundidad": 0.8}
            while i < len(toks) and toks[i] in ("tallado", "tallado_relieve", "piedra", "madera"):
                if toks[i] == "tallado_relieve":
                    carve["tipo"] = "relieve"
                elif toks[i] in ("piedra", "madera"):
                    carve["grano"] = toks[i]
                i += 1
            try:
                log.append(ops.carve_texture(data, "triskel", carve))
            except SpecError:
                if any(r.get("textura") == "triskel" for r in data.get("relieves", [])):
                    raise
                log.append(ops.add_ornament(data, "triskel", None, None, None, flat=True, carve=carve))
        elif op == "quitar":
            what = take("adornos", "cuerdas", "cadenas")
            if not what:
                raise SpecError("«quitar» necesita adornos, cuerdas o cadenas.")
            before = len(data.get("relieves", []))
            keep = []
            for r in data.get("relieves", []):
                drop = (what == "adornos" and r.get("textura") in ORNAMENTS) or (what == "cuerdas" and r.get("tipo") == "cuerda") \
                    or (what == "cadenas" and r.get("tipo") == "cadena")
                if not drop:
                    keep.append(r)
            if keep:
                data["relieves"] = keep
            else:
                data.pop("relieves", None)
            if what == "adornos":
                for name in ORNAMENTS:
                    data.get("texturas", {}).pop(name, None)
                for v in data.get("vistas", {}).values():
                    v["capas"] = [c for c in v["capas"] if c.get("textura") != "triskel"]
            log.append(f"{before - len(keep)} relieves quitados")
        else:
            raise SpecError(f"El programa tiene una orden desconocida: «{op}».")
    if not data:
        raise SpecError("El programa no produce ningún objeto.")
    return data, log
