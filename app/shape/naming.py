import unicodedata
from pathlib import Path

IMAGE_FILTER = "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp *.tga *.tif *.tiff)"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tga", ".tif", ".tiff"}
GRID_WORDS = ("malla", "grid", "mesh")
INTERIOR_WORDS = ("interior", "interna", "interno", "inside", "dentro")
INTERIOR_MOVING = ("tapa", "movil", "lid", "moving", "arriba", "top", "superior")
INTERIOR_FIXED = ("base", "fija", "fijo", "fixed", "abajo", "bottom", "inferior")

# (clave, título, palabras del nombre de archivo). Orden de la cuadrícula: 2 columnas x 3 filas.
VIEWS = (
    ("front", "Frente", ("front", "frente", "delante", "frontal")),
    ("back", "Detrás", ("back", "atras", "detras", "trasera", "posterior", "rear")),
    ("left", "Izquierda", ("left", "izq")),
    ("right", "Derecha", ("right", "der")),
    ("top", "Arriba", ("top", "arriba", "superior", "cenital")),
    ("bottom", "Abajo", ("bottom", "abajo", "inferior", "debajo")),
)
VIEW_KEYS = tuple(k for k, _, _ in VIEWS)
VIEW_NAMES = {k: t.lower() for k, t, _ in VIEWS}   # nombres para mensajes
INTERIOR_KEYS = ("movable", "fixed")                # tapa (pieza móvil) y base (pieza fija)


def normalize(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def _has(name: str, words) -> bool:
    return any(w in name for w in words)


def classify(filename: str):
    """(vista o None, es_malla) a partir del nombre del archivo. Ej.: 'pokeball_frente_malla.png' -> ('front', True)."""
    name = normalize(Path(filename).stem)
    is_grid = _has(name, GRID_WORDS)
    for key, _, words in sorted(VIEWS, key=lambda v: v[0] not in ("left", "right")):  # izquierda/derecha primero
        if _has(name, words):
            return key, is_grid
    return None, is_grid


def classify_interior(filename: str):
    """Textura interior a partir del nombre: ('movable',), ('fixed',) o ambas si no se indica la pieza. None si no es interior.
    Ej.: 'pokeball_interior_tapa.png' -> ('movable',); 'pokeball_interior_base.png' -> ('fixed',)."""
    name = normalize(Path(filename).stem)
    if not _has(name, INTERIOR_WORDS):
        return None
    moving, fixed = _has(name, INTERIOR_MOVING), _has(name, INTERIOR_FIXED)
    if moving and not fixed:
        return ("movable",)
    if fixed and not moving:
        return ("fixed",)
    return INTERIOR_KEYS


def object_name(paths) -> str:
    """Nombre del objeto: lo que queda del nombre del primer archivo al quitar la vista y 'malla'."""
    words = {w for _, _, ws in VIEWS for w in ws} | set(GRID_WORDS)
    for p in paths:
        tokens = [t for t in normalize(Path(p).stem).replace("-", "_").replace(" ", "_").split("_")
                  if t and not any(t == w or t.startswith(w) for w in words)]
        if tokens:
            return "_".join(tokens)
    return "objeto"
