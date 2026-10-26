"""Catálogo de la IA (SQLite, solo lectura): qué colores, zonas, formas, órdenes, plantillas y texturas existen en la aplicación y cómo se usan.
La IA, el ejecutor del programa y el generador de entrenamiento leen de aquí; para registrar una novedad se añade una fila (testing/ia/catalogo_cli.py)."""
import sqlite3
from functools import lru_cache

from app.utils.paths_util import CATALOG_DB


def _split(text):
    return [w.strip() for w in (text or "").split("|") if w.strip()]


@lru_cache(maxsize=1)
def cargar(ruta=None) -> dict:
    """Todo el catálogo en memoria (se lee una sola vez)."""
    path = ruta or CATALOG_DB
    if not path.exists():
        raise FileNotFoundError(f"Falta el catálogo de la IA: {path}")
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        q = lambda sql: con.execute(sql).fetchall()
        cat = {
            "colores_base": {t: (h, _split(p)) for t, h, p in q("SELECT token, hex, palabras FROM colores WHERE tipo = 'base' ORDER BY orden")},
            "colores_fijos": {t: h for t, h in q("SELECT token, hex FROM colores WHERE tipo = 'fijo' ORDER BY orden")},
            "colores_alias": {w: t for w, t in q("SELECT palabra, token FROM colores_alias")},
            "zonas": {t: (tex, _split(p), d) for t, tex, p, d in q("SELECT token, textura, palabras, descripcion FROM zonas ORDER BY orden")},
            "formas": {t: (_split(p), d) for t, p, d in q("SELECT token, palabras, descripcion FROM formas ORDER BY orden")},
            "ordenes": {t: (a, d, e) for t, a, d, e in q("SELECT token, argumentos, descripcion, ejemplo FROM ordenes ORDER BY orden")},
            "plantillas": {t: (d, p.split()) for t, d, p in q("SELECT token, descripcion, programa FROM plantillas")},
            "texturas": {t: (d, j) for t, d, j in q("SELECT tipo, descripcion, ejemplo FROM texturas ORDER BY orden")},
            "objetos": {t: (d, f) for t, d, f in q("SELECT token, descripcion, ficha FROM objetos ORDER BY orden")},
            "meta": {k: v for k, v in q("SELECT clave, valor FROM meta")},
        }
    finally:
        con.close()
    return cat


def colores_base() -> dict:
    """{color: '#rrggbb'} de los colores base (rojo, azul…)."""
    return {t: h for t, (h, _) in cargar()["colores_base"].items()}


def palabras_color() -> dict:
    """{color base: [palabras con las que se pide]}."""
    return {t: ws for t, (_, ws) in cargar()["colores_base"].items()}


def colores_fijos() -> dict:
    return dict(cargar()["colores_fijos"])


def alias_color() -> dict:
    """{palabra: color con tono} (celeste -> azul_claro…)."""
    return dict(cargar()["colores_alias"])


def zonas() -> dict:
    """{zona: textura del JSON}."""
    return {t: tex for t, (tex, _, _) in cargar()["zonas"].items()}


def palabras_zona() -> dict:
    return {t: ws for t, (_, ws, _) in cargar()["zonas"].items()}


def formas() -> set:
    return set(cargar()["formas"])


def palabras_forma() -> dict:
    return {t: ws for t, (ws, _) in cargar()["formas"].items() if ws}


def plantilla(token) -> list:
    """Fichas del programa que sustituye una macro (starter)."""
    return list(cargar()["plantillas"][token][1])


def referencias() -> dict:
    """{nombre: (alias, descripcion, alto_m, ancho_m, fondo_m)}: objetos que el usuario registró con sus propias imágenes o modelos."""
    con = sqlite3.connect(f"file:{CATALOG_DB.as_posix()}?mode=ro", uri=True)
    try:
        return {n: (_split(a.replace(",", "|")), d, h, w, f) for n, a, d, h, w, f in
                con.execute("SELECT nombre, alias, descripcion, alto_m, ancho_m, fondo_m FROM referencias")}
    finally:
        con.close()


def referencia_objeto(nombre) -> dict:
    """JSON del objeto de una referencia registrada."""
    import json
    con = sqlite3.connect(f"file:{CATALOG_DB.as_posix()}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT objeto FROM referencias WHERE nombre = ?", (nombre,)).fetchone()
    finally:
        con.close()
    if not row:
        raise KeyError(nombre)
    return json.loads(row[0])
