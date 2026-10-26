"""Palabras de color que entiende la IA: sirven para entrenarla y para comprobar que solo se cambian los colores que el usuario nombró."""
from app.ai.fast import catalogo

COL = catalogo.palabras_color()          # ficha de color -> palabras con las que se pide (tabla colores del catálogo)
SPECIAL = catalogo.alias_color()         # celeste -> azul_claro… (tabla colores_alias)
WORD_BASE = {w: base for base, ws in COL.items() for w in ws} | {w: tok.split("_")[0] for w, tok in SPECIAL.items()}


def bases_in(words) -> set:
    """Colores base (rojo, azul…) que nombran estas palabras."""
    return {WORD_BASE[w] for w in words if w in WORD_BASE}
