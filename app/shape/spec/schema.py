"""Objeto descrito en un único archivo JSON (formato "janus.objeto/1"): lectura y validación.

El JSON sustituye por completo a las vistas y las mallas: da las medidas, cómo se ve cada vista (capas con texturas),
las marcas (corte, bisagra, botón, salientes, huesos) y las texturas interiores. La forma 3D se calcula a partir de él
(spec.blueprint); las imágenes que ve el usuario son solo una vista previa (spec.preview).

Estructura (todas las medidas en METROS):

{
  "formato": "janus.objeto/1",
  "nombre": "pokeball",
  "medidas_m": {"ancho": 0.2, "alto": 0.2, "fondo": 0.2},
  "texturas": {                                   # materiales con nombre
    "rojo":  {"color": "#d62d20"},
    "cielo": {"degradado": {"desde": "#ffffff", "hasta": "#3070e0", "angulo": 90}},       # 90° = de abajo a arriba
    "foco":  {"degradado": {"desde": "#ffffff", "hasta": "#303030", "tipo": "radial"}},   # del centro al borde
    "madera": {"veta": {"claro": "#eecd9c", "oscuro": "#cda472", "escala_m": 0.012, "semilla": 3}}
  },
  "sombreado": {"luz": [-0.45, 0.6, 0.65], "base": 0.66, "intensidad": 0.4},    # opcional; luz respecto a la cámara
  "contorno": {"color": "#1c1c22", "grosor_m": 0.0015},                          # opcional (silueta de cada vista)
  "vistas": {                                     # frente, detras, izquierda, derecha, arriba, abajo (frente y una lateral obligatorias)
    "frente": {"capas": [
        {"textura": "rojo", "forma": "circulo", "centro": [0.1, 0.1], "radio": 0.1, "silueta": true, "sombrear": true}
    ]}
  },
  "relieves": [                                   # (opcional) piezas que sobresalen de un cuerpo esférico y siguen su curvatura
    {"tipo": "franja", "textura": "oro", "radio_m": 0.125,      # radio de la esfera (centrada en la caja, apoyada en el suelo)
     "inclinacion_grados": 45, "ancho_m": 0.04, "sobresale_m": 0.012,
     "margen_m": 0.07,                           # altura mínima sobre la línea de corte (deja libre la banda y el botón)
     "simetrica": true},                         # true = una a cada lado (izquierda y derecha)
    {"tipo": "cadena", "textura": "rojo", "radio_m": 0.125, "altura_m": 0.07,   # anillo de eslabones paralelo a la banda
     "eslabones": 28, "largo_m": 0.03, "ancho_m": 0.014, "grosor_m": 0.005}
  ],
  "marcas": {
    "corte":     [{"vista": "derecha", "linea": [[0, 0.1], [0.2, 0.1]]}],         # por aquí se abre
    "mueve":     [{"vista": "derecha", "punto": [0.1, 0.15]}],                     # (opcional) lado que se mueve
    "bisagra":   [{"vista": "derecha", "punto": [0.004, 0.1]}],                    # (opcional) pivote
    "boton":     [{"vista": "frente", "centro": [0.1, 0.1], "radio": 0.03}],       # queda entero en la tapa
    "salientes": [{"vista": "frente", "forma": "circulo", "centro": [0.1, 0.1], "radio": 0.1}],   # huella de lo que sobresale
    "huesos":    [{"id": 0, "padre": null, "frente": [0.1, 0.1], "derecha": [0.1, 0.1]},
                  {"id": 1, "padre": 0, "frente": [0.1, 0.15]}]                    # esqueleto: ids 0-59, padre null = raíz
  },
  "interior": {                                   # (opcional) texturas de dentro de la tapa y de la base
    "tapa": {"lado_m": 0.2, "circular": true, "capas": [ ... ]},
    "base": {"lado_m": 0.2, "circular": true, "capas": [ ... ]}
  }
}

Capas (se dibujan en orden): "forma" = circulo (centro, radio) | elipse (centro, radios [rx, ry]) | rect (esquina [x, y],
tamano [ancho, alto], radio_esquina) | poligono (puntos) | linea (puntos, grosor). Opciones: "textura" (nombre),
"silueta": true (la capa forma parte de la silueta: lo demás solo se pinta dentro de ella), "recorte": [x0, y0, x1, y1],
"borde": {"color", "grosor_m"}, "sombrear": true (círculo/elipse sombreado como una esfera).

Coordenadas de cada vista: como en la imagen, origen abajo a la izquierda del cuadro que ocupa el objeto en esa vista.
  frente/detras: x = ancho, y = alto · derecha (el frente mira a la derecha) / izquierda (el frente mira a la izquierda):
  x = fondo, y = alto · arriba (el frente abajo) / abajo (el frente arriba): x = ancho, y = fondo."""
import json
import re
from pathlib import Path

from app.shape.geometry.relief import KINDS as RELIEF_KINDS
from app.shape.rig.skeleton import PALETTE

FORMAT = "janus.objeto/1"
CANVAS = 640                # lienzo de la vista previa (píxeles)
FILL = 0.94                 # fracción del lienzo que ocupa la dimensión mayor del objeto
MIN_SIDE_PX = 12            # la dimensión menor debe ocupar al menos estos píxeles
VIEW_KEYS = {"frente": "front", "detras": "back", "izquierda": "left", "derecha": "right", "arriba": "top", "abajo": "bottom"}
VIEW_NAMES = {v: k for k, v in VIEW_KEYS.items()}
INTERIOR_KEYS = {"tapa": "movable", "base": "fixed"}
SHAPES = ("circulo", "elipse", "rect", "poligono", "linea")
MARK_KINDS = ("corte", "mueve", "bisagra", "boton", "salientes")


class SpecError(ValueError):
    """Error de contenido del JSON, con un mensaje pensado para mostrarse tal cual."""


def parse_color(value, where):
    v = str(value).lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{3}", v):
        v = "".join(c * 2 for c in v)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", v):
        raise SpecError(f"{where}: color no válido ({value!r}); usa el formato #rrggbb.")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def parse_point(value, where):
    if not (isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(c, (int, float)) for c in value)):
        raise SpecError(f"{where}: se esperaba un punto [x, y] en metros.")
    return float(value[0]), float(value[1])


def _texture(name, t):
    where = f"texturas.{name}"
    if "color" in t:
        return {"color": parse_color(t["color"], where)}
    if "degradado" in t:
        g = t["degradado"]
        return {"desde": parse_color(g.get("desde"), where + ".desde"), "hasta": parse_color(g.get("hasta"), where + ".hasta"),
                "angulo": float(g.get("angulo", 90)), "radial": g.get("tipo") == "radial"}
    if "veta" in t:
        v = t["veta"]
        return {"claro": parse_color(v.get("claro"), where + ".claro"), "oscuro": parse_color(v.get("oscuro"), where + ".oscuro"),
                "escala": max(float(v.get("escala_m", 0.012)), 1e-4), "semilla": int(v.get("semilla", 1))}
    raise SpecError(f"{where}: falta «color», «degradado» o «veta».")


class ObjectSpec:
    def __init__(self, data: dict):
        self.data = data
        self.name = str(data.get("nombre") or "objeto")
        m = data.get("medidas_m") or {}
        try:
            self.width, self.height, self.depth = float(m["ancho"]), float(m["alto"]), float(m["fondo"])
        except Exception:
            raise SpecError("Falta «medidas_m» con «ancho», «alto» y «fondo» en metros.")
        dims = (self.width, self.height, self.depth)
        if not all(v > 0 for v in dims):
            raise SpecError("Las medidas de «medidas_m» deben ser mayores que 0.")
        self.ppm = FILL * CANVAS / max(dims)       # píxeles por metro: el objeto siempre llena el lienzo igual
        if min(dims) * self.ppm < MIN_SIDE_PX:
            raise SpecError(f"Las proporciones son demasiado extremas: la medida menor ({min(dims):g} m) es más de "
                            f"{FILL * CANVAS / MIN_SIDE_PX:.0f} veces menor que la mayor ({max(dims):g} m).")
        self.textures = {k: _texture(k, t) for k, t in (data.get("texturas") or {}).items()}
        self.light = data.get("sombreado") or {}
        self.outline = data.get("contorno")
        if self.outline:
            parse_color(self.outline.get("color", "#1c1c22"), "contorno")
        self.views = data.get("vistas") or {}
        for key, view in self.views.items():
            if key not in VIEW_KEYS:
                raise SpecError(f"Vista desconocida «{key}». Usa: {', '.join(VIEW_KEYS)}.")
            self._check_layers(view.get("capas"), f"vistas.{key}", silhouette=True)
        if "frente" not in self.views or not ({"izquierda", "derecha"} & set(self.views)):
            raise SpecError("Hacen falta al menos la vista «frente» y una lateral («izquierda» o «derecha»).")
        self.reliefs = data.get("relieves") or []
        self._check_reliefs()
        self.marks = data.get("marcas") or {}
        self.interior = data.get("interior") or {}
        for key, block in self.interior.items():
            if key not in INTERIOR_KEYS:
                raise SpecError(f"Interior desconocido «{key}». Usa: {', '.join(INTERIOR_KEYS)}.")
            self._check_layers(block.get("capas"), f"interior.{key}")
        self._check_marks()

    def _check_layers(self, layers, where, silhouette=False):
        if not isinstance(layers, list) or not layers:
            raise SpecError(f"{where}: falta la lista «capas».")
        if silhouette and not any(c.get("silueta") for c in layers):
            raise SpecError(f"{where}: ninguna capa tiene «silueta»: true.")
        for i, c in enumerate(layers):
            self.check_shape(c, f"{where}.capas[{i}]")
            if c.get("textura") not in self.textures:
                raise SpecError(f"{where}.capas[{i}]: la textura {c.get('textura')!r} no existe en «texturas».")

    @staticmethod
    def check_shape(c, w):
        shape = c.get("forma", "circulo")
        if shape not in SHAPES:
            raise SpecError(f"{w}: forma desconocida {shape!r}. Usa: {', '.join(SHAPES)}.")
        if shape in ("circulo", "elipse"):
            parse_point(c.get("centro"), w + ".centro")
            if shape == "circulo" and not isinstance(c.get("radio"), (int, float)):
                raise SpecError(f"{w}: falta el «radio» en metros.")
            if shape == "elipse":
                parse_point(c.get("radios"), w + ".radios")
        elif shape in ("poligono", "linea"):
            if not isinstance(c.get("puntos"), list) or len(c["puntos"]) < 2:
                raise SpecError(f"{w}: faltan los «puntos».")
            [parse_point(p, w + ".puntos") for p in c["puntos"]]
        else:
            parse_point(c.get("esquina"), w + ".esquina")
            parse_point(c.get("tamano"), w + ".tamano")

    def _check_reliefs(self):
        if not isinstance(self.reliefs, list):
            raise SpecError("«relieves» debe ser una lista.")
        for i, r in enumerate(self.reliefs):
            where = f"relieves[{i}]"
            if r.get("tipo") not in RELIEF_KINDS:
                raise SpecError(f"{where}: «tipo» debe ser: {', '.join(RELIEF_KINDS)}.")
            if r.get("textura") not in self.textures:
                raise SpecError(f"{where}: la textura {r.get('textura')!r} no existe en «texturas».")
            if not isinstance(r.get("radio_m"), (int, float)) or r["radio_m"] <= 0:
                raise SpecError(f"{where}: falta «radio_m» (radio de la esfera en metros).")
            for key, default in RELIEF_KINDS[r["tipo"]].items():
                v = r.get(key, default)
                if isinstance(default, bool):
                    continue
                if not isinstance(v, (int, float)) or v <= 0:
                    raise SpecError(f"{where}: «{key}» debe ser un número mayor que 0" + (" (en metros)." if key.endswith("_m") else "."))

    def _check_marks(self):
        for kind in MARK_KINDS:
            for item in self.marks.get(kind, []):
                if item.get("vista") not in VIEW_KEYS:
                    raise SpecError(f"marcas.{kind}: falta la «vista» (o no existe).")
                if kind == "corte":
                    [parse_point(p, "marcas.corte.linea") for p in item.get("linea") or [None]]
                elif kind in ("mueve", "bisagra"):
                    parse_point(item.get("punto"), f"marcas.{kind}.punto")
                elif kind == "boton":
                    parse_point(item.get("centro"), "marcas.boton.centro")
                else:
                    self.check_shape(item, "marcas.salientes")
        for b in self.marks.get("huesos", []):
            if not isinstance(b.get("id"), int) or not 0 <= b["id"] < len(PALETTE):
                raise SpecError(f"marcas.huesos: «id» entre 0 y {len(PALETTE) - 1}.")
            if b.get("padre") is not None and not (isinstance(b["padre"], int) and 0 <= b["padre"] < len(PALETTE)):
                raise SpecError(f"marcas.huesos: «padre» no válido en el hueso {b['id']}.")
            for view in VIEW_KEYS:
                if view in b:
                    parse_point(b[view], f"marcas.huesos[{b['id']}].{view}")

    def size(self, view):
        """(ancho, alto) en metros del cuadro que ocupa el objeto en esa vista (nombre en español)."""
        if view in ("frente", "detras"):
            return self.width, self.height
        if view in ("izquierda", "derecha"):
            return self.depth, self.height
        return self.width, self.depth

    def origin(self, view):
        """Esquina inferior izquierda de ese cuadro en el lienzo de la vista previa (metros, objeto centrado; el lienzo mide CANVAS / ppm metros)."""
        w, h = self.size(view)
        return (CANVAS / self.ppm - w) / 2, (CANVAS / self.ppm - h) / 2

    @property
    def has_skeleton(self):
        return bool(self.marks.get("huesos"))


def load_spec(source) -> ObjectSpec:
    """Lee el JSON (ruta o texto) y lo valida. Lanza SpecError con un mensaje claro si algo falla."""
    text = source
    if isinstance(source, Path) or (isinstance(source, str) and len(source) < 500 and "\n" not in source and Path(source).is_file()):
        text = Path(source).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise SpecError(f"El archivo no es un JSON válido (línea {e.lineno}, columna {e.colno}): {e.msg}.")
    if not isinstance(data, dict) or data.get("formato") != FORMAT:
        raise SpecError(f"El archivo no es un objeto de JanusApp: falta «formato»: «{FORMAT}».")
    return ObjectSpec(data)
