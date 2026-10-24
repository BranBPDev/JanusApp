"""Palabras de color que entiende la IA: sirven para entrenarla y para comprobar que solo se cambian los colores que el usuario nombró."""
COL = {  # ficha de color -> palabras con las que se pide
    "rojo": ["rojo", "roja", "carmesi", "escarlata", "colorado"], "azul": ["azul"], "verde": ["verde"],
    "amarillo": ["amarillo", "amarilla"], "naranja": ["naranja", "anaranjado", "anaranjada"],
    "morado": ["morado", "morada", "violeta", "purpura", "lila"], "rosa": ["rosa", "rosado", "rosada"],
    "negro": ["negro", "negra"], "blanco": ["blanco", "blanca"], "gris": ["gris", "plomo"],
    "marron": ["marron", "cafe", "chocolate"], "dorado": ["dorado", "dorada", "oro"], "plateado": ["plateado", "plateada", "plata"],
    "turquesa": ["turquesa", "cian"], "beige": ["beige", "crema"],
}
SPECIAL = {"celeste": "azul_claro", "granate": "rojo_oscuro", "marino": "azul_oscuro", "burdeos": "rojo_oscuro", "esmeralda": "verde_oscuro",
           "fucsia": "rosa_oscuro", "salmon": "naranja_claro", "mostaza": "amarillo_oscuro", "lima": "verde_claro"}
WORD_BASE = {w: base for base, ws in COL.items() for w in ws} | {w: tok.split("_")[0] for w, tok in SPECIAL.items()}


def bases_in(words) -> set:
    """Colores base (rojo, azul…) que nombran estas palabras."""
    return {WORD_BASE[w] for w in words if w in WORD_BASE}
