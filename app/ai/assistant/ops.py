"""Operaciones que la IA escribe (pocas fichas) y que se aplican sobre el JSON del objeto: siempre sobre una copia.

La IA decide QUÉ hacer; aquí se hace con la geometría exacta del formato (centrar la esfera, dejar margen a los relieves, sustituir la
banda por una cuerda o cadena del mismo grosor y rodeando el botón, escalar, etc.)."""
import copy
import math

from app.ai.assistant import ejemplos
from app.shape.spec.schema import FORMAT, SpecError, parse_color

r5 = lambda v: round(float(v), 5)
NO_SCALE = {"eje", "luz", "angulo", "semilla", "inclinacion_grados", "eslabones", "id", "padre", "base", "intensidad", "formato", "nombre",
            "hebras", "vueltas", "copias", "lat_grados", "lon_grados", "giro_grados", "paso_grados"}
SCALE_KEYS = {"centro", "radio", "radios", "esquina", "tamano", "puntos", "linea", "punto", "grosor", "radio_esquina", "recorte",
              "frente", "detras", "izquierda", "derecha", "arriba", "abajo", "curvas", "vertices", "tamano_m"}
VIEWS = ("frente", "detras", "izquierda", "derecha", "arriba", "abajo")
SIDE_VIEWS = ("frente", "detras", "izquierda", "derecha")


def hexcolor(value, where):
    r, g, b = parse_color(value, where)
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------- utilidades de geometría ----------
def _scale(node, k, key=None):
    if isinstance(node, dict):
        for name, v in list(node.items()):
            if name in NO_SCALE:
                continue
            if name == "medidas_m":
                node[name] = {a: r5(x * k) for a, x in v.items()}
            elif isinstance(v, (dict, list)) and name not in SCALE_KEYS and not name.endswith("_m"):
                _scale(v, k, name)
            else:
                node[name] = _scale_value(v, k, name)
    elif isinstance(node, list):
        for v in node:
            if isinstance(v, (dict, list)):
                _scale(v, k, key)


def _scale_value(v, k, name):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return r5(v * k) if (name in SCALE_KEYS or name.endswith("_m")) else v
    if isinstance(v, list):
        return [_scale_value(x, k, name) for x in v]
    if isinstance(v, dict):
        _scale(v, k)
    return v


def radius(spec) -> float:
    """Radio de la esfera del objeto (la capa circular de silueta de la vista frente)."""
    for c in (spec.get("vistas", {}).get("frente", {}).get("capas") or []):
        if c.get("forma") == "circulo" and c.get("silueta"):
            return float(c["radio"])
    m = spec.get("medidas_m", {})
    return min(m.get("ancho", 0.25), m.get("alto", 0.25), m.get("fondo", 0.25)) / 2


def _shift_xy(layer, dx, dy):
    if "centro" in layer:
        layer["centro"] = [r5(layer["centro"][0] + dx), r5(layer["centro"][1] + dy)]
    if "esquina" in layer:
        layer["esquina"] = [r5(layer["esquina"][0] + dx), r5(layer["esquina"][1] + dy)]
    if "puntos" in layer:
        layer["puntos"] = [[r5(x + dx), r5(y + dy)] for x, y in layer["puntos"]]


def set_margin(spec, pad):
    """Deja 'pad' metros de margen a cada lado de la esfera (ancho y fondo = D + 2·pad), recentrándola; solo crece."""
    D = 2 * radius(spec)
    m = spec["medidas_m"]
    new = r5(D + 2 * pad)
    if new <= m["ancho"] + 1e-9:
        return
    dx = (new - m["ancho"]) / 2
    for name, view in spec["vistas"].items():
        top = name in ("arriba", "abajo")
        for c in view["capas"]:
            _shift_xy(c, dx, dx if top else 0)
            if c.get("forma") == "rect" and c.get("tamano", [0, 0])[0] >= m["ancho"] - 1e-6:
                c["tamano"][0] = r5(c["tamano"][0] + 2 * dx)
                c["esquina"][0] = 0
            if "recorte" in c:
                x0, y0, x1, y1 = c["recorte"]
                c["recorte"] = [0 if x0 <= 1e-9 else r5(x0 + dx), y0, r5(x1 + 2 * dx), y1]
    marks = spec.get("marcas") or {}
    for key in ("mueve", "boton"):
        for it in marks.get(key, []):
            if "punto" in it:
                it["punto"][0] = r5(it["punto"][0] + dx)
            if "centro" in it:
                it["centro"][0] = r5(it["centro"][0] + dx)
    for it in marks.get("corte", []):
        it["linea"] = [[0, it["linea"][0][1]], [new, it["linea"][1][1]]]
    for it in marks.get("bisagra", []):
        it["punto"][0] = r5(pad + 0.005)
    for it in marks.get("salientes", []):
        _shift_xy(it, dx, 0)
    m["ancho"] = m["fondo"] = new


def set_height(spec, alto):
    """Sube el alto del objeto (para lo que sobresale por arriba) y alarga el recorte de la tapa."""
    m = spec["medidas_m"]
    if alto <= m["alto"] + 1e-9:
        return
    m["alto"] = r5(alto)
    for name in SIDE_VIEWS:
        for c in spec["vistas"][name]["capas"]:
            if "recorte" in c:
                c["recorte"][3] = r5(alto)


def _texture(spec, name, color):
    spec.setdefault("texturas", {})[name] = {"color": hexcolor(color, f"textura {name}")}


def _rope_params(R, h, kind, ring, count=None):
    """Parámetros de una cuerda o cadena de grosor h (mismo que la banda) sobre un aro de radio 'ring'."""
    if kind == "cuerda":
        return {"grosor_m": r5(h), "hebras": 3, "vueltas": count or max(8, round(2 * math.pi * ring / (1.5 * h)))}
    link = 2.2 * h
    return {"eslabones": count or max(6, round(2 * math.pi * ring / (0.7 * link))), "largo_m": r5(link), "ancho_m": r5(h), "grosor_m": r5(h / 3)}


def _chord(R, axis_dist):
    """Distancia (recta) desde el polo hasta el punto de la esfera que está a 'axis_dist' del eje."""
    return 2 * R * math.sin(math.asin(min(axis_dist / R, 0.999)) / 2)


def band_by(spec, kind, color=None):
    """Sustituye la banda por una cuerda/cadena del mismo grosor y en su posición (en la tapa, sobre el corte), con un segundo aro del
    mismo tipo rodeando el borde del botón; el aro del ecuador queda abierto y toca al del botón."""
    if kind not in ("cuerda", "cadena"):
        raise SpecError("banda_por: «tipo» debe ser cuerda o cadena.")
    R = radius(spec)
    band = next((c for c in spec["vistas"]["lateral" if "lateral" in spec["vistas"] else "derecha"]["capas"]
                 if c.get("textura") == "banda" and c.get("forma") == "rect"), None)
    if band is None:
        band = next((c for v in spec["vistas"].values() for c in v["capas"] if c.get("textura") == "banda" and c.get("forma") == "rect"), None)
    if band is None:
        raise SpecError("banda_por: el objeto no tiene banda que sustituir.")
    h = float(band["tamano"][1])
    button = next((c for c in spec["vistas"]["frente"]["capas"] if c.get("textura") == "cierre" and c.get("forma") == "circulo"), None)
    rb = float(button["radio"]) if button else 0.128 * 2 * R
    for view in spec["vistas"].values():
        view["capas"] = [c for c in view["capas"] if c.get("textura") != "banda"]
    name = kind
    _texture(spec, name, color or spec["texturas"].get("banda", {}).get("color", "#222224"))
    spec["relieves"] = [r for r in spec.get("relieves", []) if r.get("textura") != name]
    y0 = (h / 2 + 0.0003) / (1 + h / (2 * R))
    ring_eq = math.sqrt(R * R - y0 * y0)
    rho = rb + h * 0.2
    hole = r5(_chord(R, rho + h / 2) * 0.9)
    eq = {"tipo": kind, "textura": name, "radio_m": r5(R), "eje": [0, 1, 0], "radio_aro_m": r5(ring_eq), **_rope_params(R, h, kind, ring_eq),
          "hueco": {"eje": [0, 0, 1], "radio_m": hole}}
    bt = {"tipo": kind, "textura": name, "radio_m": r5(R), "eje": [0, 0, 1], "radio_aro_m": r5(rho), **_rope_params(R, h, kind, rho)}
    spec["relieves"] += [eq, bt]
    set_margin(spec, h * 0.99)
    for it in (spec.get("marcas") or {}).get("boton", []):
        it["radio"] = r5(rb + h * 1.2)
    return f"banda → {kind} de {h * 1000:.1f} mm"


def convert_reliefs(spec, src, dst, color=None):
    """Convierte los relieves de un tipo (cadena) en otro (cuerda) conservando eje, aro, hueco, color y grosor equivalente."""
    n = 0
    for r in spec.get("relieves", []):
        if r.get("tipo") != src:
            continue
        old = dict(r)
        for k in list(r):
            if k not in ("tipo", "textura", "radio_m", "eje", "radio_aro_m", "hueco"):
                del r[k]
        r["tipo"] = dst
        ring = float(old.get("radio_aro_m", 0.1))
        w = float(old.get("ancho_m") or old.get("grosor_m") or 0.012)
        if dst == "cuerda":
            r.update(_rope_params(radius(spec), w, "cuerda", ring, int(old.get("eslabones", 0)) or None))
        else:
            r.update(_rope_params(radius(spec), w, "cadena", ring))
        n += 1
    if not n:
        raise SpecError(f"convertir: no hay relieves de tipo {src}.")
    if color:
        for r in spec["relieves"]:
            if r["tipo"] == dst:
                _texture(spec, r["textura"], color)
    return f"{n} relieves {src} → {dst}"


# ---------- adornos ----------
def triskel_arm(size):
    """Un brazo del triskel celta (triple espiral): la cola sale del centro, sube por el lado de la espiral y se enrolla hacia dentro
    (~1,5 vueltas). Medidas en metros sobre la superficie; 'size' = diámetro total del triskel. El brazo apunta a +x."""
    rho0 = size / 5.48                                     # radio de la espiral; centro de la espiral a 1,55·rho0 del centro del triskel
    Dc = 1.55
    P = [(0.0, 0.0), (0.1, 0.55), (1.0, 0.7), (1.0, Dc)]  # cola (Bézier cúbica) en unidades de rho0, brazo hacia +y
    pts = []
    for i in range(11):
        t = i / 10
        pts.append([sum(c * q[k] for c, q in zip(((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3), P)) for k in (0, 1)])
    n, turns = 44, 1.15
    for i in range(1, n + 1):
        th = 2 * math.pi * turns * i / n
        rr = 1.0 - 0.8 * (i / n) ** 0.9
        pts.append([rr * math.cos(th), Dc + rr * math.sin(th)])
    # giro de -90°: el brazo pasa a apuntar a +x (rotación, no espejo)
    return [[r5(y * rho0), r5(-x * rho0)] for x, y in pts]


PIECES = {"anillo": ("toro", 0.8, 0.35), "bola": ("esfera", 0.45, 1.0), "cono": ("cono", 0.6, 1.0), "cilindro": ("cilindro", 0.5, 1.0)}


def add_ornament(spec, shape, color=None, size=None, count=None, kind_color_from="cuerda", flat=False):
    R = radius(spec)
    spec.setdefault("relieves", [])
    if shape == "triskel":
        size = float(size or 1.35 * R)
        col = color or (spec.get("texturas", {}).get(kind_color_from, {}).get("color")) or "#b3202a"
        _texture(spec, "triskel", col)
        spec["relieves"] = [r for r in spec["relieves"] if r.get("textura") != "triskel"]
        top = spec["vistas"]["arriba"]["capas"]
        top[:] = [c for c in top if c.get("textura") != "triskel"]
        if flat:      # dibujado en la textura de la tapa (vista de arriba), sin relieve
            cx, cy = spec["medidas_m"]["ancho"] / 2, spec["medidas_m"]["fondo"] / 2
            arm = triskel_arm(size)
            for k in range(3):
                a = math.radians(120 * k)
                pts = [[r5(cx + x * math.cos(a) - y * math.sin(a)), r5(cy + x * math.sin(a) + y * math.cos(a))] for x, y in arm]
                top.append({"textura": "triskel", "forma": "linea", "puntos": pts, "grosor": r5(size * 0.09)})
            return f"triskel de {size * 100:.0f} cm dibujado en la tapa (sin relieve)"
        width, rise = r5(size * 0.09), r5(size * 0.06)
        spec["relieves"].append({"tipo": "trazo", "textura": "triskel", "radio_m": r5(R), "lat_grados": 90, "lon_grados": 0, "giro_grados": 0,
                                 "curvas": [triskel_arm(size)], "ancho_m": width, "sobresale_m": rise, "copias": 3, "paso_grados": 120})
        set_height(spec, 2 * R + rise + 0.001)
        return f"triskel de {size * 100:.0f} cm sobresaliendo, centrado arriba"
    if shape in ("pinchos", "conos"):
        n = int(count or 6)
        _texture(spec, "pinchos", color or "#d9a928")
        s = R / 0.125
        spec["relieves"] = [r for r in spec["relieves"] if r.get("textura") != "pinchos"]
        spec["relieves"].append({"tipo": "pieza", "textura": "pinchos", "radio_m": r5(R), "forma": "cono", "lat_grados": 55,
                                 "tamano_m": [r5(0.03 * s), r5(0.03 * s), r5(0.04 * s)], "copias": n})
        set_margin(spec, 0.014 * s)
        set_height(spec, 2 * R + 0.04 * s * 0.9)
        return f"{n} pinchos"
    if shape in PIECES:
        d = float(size or PIECES[shape][1] * R)
        h = d * PIECES[shape][2]
        _texture(spec, "adorno", color or "#d9a928")
        spec["relieves"] = [r for r in spec["relieves"] if r.get("textura") != "adorno"]
        spec["relieves"].append({"tipo": "pieza", "textura": "adorno", "radio_m": r5(R), "forma": PIECES[shape][0], "lat_grados": 90,
                                 "tamano_m": [r5(d), r5(d), r5(h)], "hunde_m": r5(min(0.004, h / 3))})
        set_height(spec, 2 * R + h + 0.001)
        return f"{shape} de {d * 100:.0f} cm arriba"
    raise SpecError("adorno: «forma» debe ser triskel, pinchos, anillo, bola, cono o cilindro.")


# ---------- paths ----------
def _walk(root, path, create=False):
    parts = [p for p in str(path).split(".") if p != ""]
    if not parts:
        raise SpecError("Ruta vacía.")
    node = root
    for p in parts[:-1]:
        node = _child(node, p, create, path)
    return node, _key(node, parts[-1], path)


def _key(node, p, path):
    if isinstance(node, list):
        if not p.lstrip("-").isdigit() or not (-len(node) <= int(p) <= len(node)):
            raise SpecError(f"La ruta «{path}» no existe (índice {p}).")
        return int(p)
    return p


def _child(node, p, create, path):
    if isinstance(node, list):
        k = _key(node, p, path)
        if k >= len(node):
            raise SpecError(f"La ruta «{path}» no existe (índice {p}).")
        return node[k]
    if isinstance(node, dict):
        if p not in node:
            if not create:
                raise SpecError(f"La ruta «{path}» no existe («{p}»).")
            node[p] = {}
        return node[p]
    raise SpecError(f"La ruta «{path}» atraviesa un valor que no es objeto ni lista.")


def _short(v):
    s = v if isinstance(v, str) else repr(v)
    return s if len(s) <= 60 else s[:57] + "..."


def apply_ops(spec: dict, ops) -> tuple:
    """(nuevo_spec, lista de cambios en texto)."""
    if not isinstance(ops, list) or not ops:
        raise SpecError("«ops» debe ser una lista con al menos una operación.")
    data, log = copy.deepcopy(spec) if spec else {}, []
    for i, op in enumerate(ops):
        if not isinstance(op, dict):
            raise SpecError(f"ops[{i}]: debe ser un objeto.")
        kind, w = op.get("op"), f"ops[{i}]"
        if kind == "base":
            name = op.get("ejemplo")
            if name not in ejemplos.NAMES:
                raise SpecError(f"{w}: «ejemplo» debe ser: {', '.join(ejemplos.NAMES)}.")
            data = ejemplos.ejemplo(name)
            D = op.get("diametro_m")
            if D is not None:
                if isinstance(D, bool) or not isinstance(D, (int, float)) or not 0.02 <= D <= 3:
                    raise SpecError(f"{w}.diametro_m: entre 0.02 y 3 metros.")
                _scale(data, float(D) / 0.25)
            if op.get("nombre"):
                data["nombre"] = str(op["nombre"])[:60]
            log.append(f"objeto nuevo desde «{name}»")
            continue
        if not data:
            raise SpecError(f"{w}: no hay objeto; empieza con la operación «base».")
        if kind == "color":
            name = op.get("textura")
            tex = (data.get("texturas") or {}).get(name)
            if tex is None:
                raise SpecError(f"{w}: no existe la textura «{name}». Existen: {', '.join(data.get('texturas', {}))}.")
            new = hexcolor(op.get("valor"), f"{w}.valor")
            if "color" in tex:
                log.append(f"textura {name}: {tex['color']} → {new}")
                tex["color"] = new
            elif "degradado" in tex:
                log.append(f"textura {name}: degradado → {new}")
                tex["degradado"]["desde"] = tex["degradado"]["hasta"] = new
            else:
                raise SpecError(f"{w}: la textura «{name}» no tiene un color simple.")
        elif kind == "escalar":
            k = op.get("factor")
            if isinstance(k, bool) or not isinstance(k, (int, float)) or not 0.05 <= k <= 20:
                raise SpecError(f"{w}.factor: debe estar entre 0.05 y 20.")
            _scale(data, float(k))
            log.append(f"escala ×{k:g}")
        elif kind == "banda_por":
            log.append(band_by(data, op.get("tipo"), op.get("color") and hexcolor(op["color"], f"{w}.color")))
        elif kind == "convertir_relieves":
            log.append(convert_reliefs(data, op.get("de", "cadena"), op.get("a", "cuerda"), op.get("color") and hexcolor(op["color"], f"{w}.color")))
        elif kind == "adorno":
            log.append(add_ornament(data, op.get("forma"), op.get("color") and hexcolor(op["color"], f"{w}.color"), op.get("tamano_m"), op.get("cantidad")))
        elif kind == "relieve":
            val = copy.deepcopy(op.get("valor"))
            if not isinstance(val, dict):
                raise SpecError(f"{w}: «valor» debe ser el relieve completo.")
            val.setdefault("radio_m", r5(radius(data)))
            col = val.pop("color", None)
            if val.get("textura") is None:
                val["textura"] = f"relieve{len(data.get('relieves', [])) + 1}"
            if col is not None:
                _texture(data, val["textura"], col)
            data.setdefault("relieves", []).append(val)
            set_margin(data, 0.014 * radius(data) / 0.125)
            log.append(f"relieve {val.get('tipo')} añadido")
        elif kind == "quitar_relieves":
            before = len(data.get("relieves", []))
            data["relieves"] = [r for r in data.get("relieves", []) if op.get("tipo") not in (None, r.get("tipo")) or op.get("textura") not in (None, r.get("textura"))
                                if not (op.get("tipo") is None and op.get("textura") is None)]
            if not data["relieves"]:
                data.pop("relieves")
            log.append(f"{before - len(data.get('relieves', []))} relieves quitados")
        elif kind in ("poner", "añadir", "quitar"):
            node, key = _walk(data, op.get("ruta"), create=(kind == "poner"))
            if kind == "poner":
                if "valor" not in op:
                    raise SpecError(f"{w}: falta «valor».")
                if isinstance(node, list) and key >= len(node):
                    raise SpecError(f"{w}: índice fuera de rango.")
                old = node[key] if (isinstance(node, list) or key in node) else None
                node[key] = op["valor"]
                log.append(f"{op['ruta']}: {_short(old)} → {_short(op['valor'])}")
            elif kind == "añadir":
                target = node[key] if (isinstance(node, list) or key in node) else None
                if target is None:
                    node[key] = target = []
                if not isinstance(target, list) or "valor" not in op:
                    raise SpecError(f"{w}: «añadir» necesita una lista en «{op.get('ruta')}» y un «valor».")
                target.append(op["valor"])
                log.append(f"añadido a {op['ruta']}: {_short(op['valor'])}")
            else:
                if isinstance(node, list) and not 0 <= key < len(node) or isinstance(node, dict) and key not in node:
                    raise SpecError(f"{w}: la ruta «{op.get('ruta')}» no existe.")
                del node[key]
                log.append(f"quitado {op['ruta']}")
        else:
            raise SpecError(f"{w}: operación «{kind}» desconocida.")
    data.setdefault("formato", FORMAT)
    return data, log
