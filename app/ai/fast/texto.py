"""Texto → fichas: normalización, literales (colores #hex y medidas) pasados como marcadores <h0>.. y <n0>.., y vocabulario."""
import difflib
import re
import unicodedata

HEX = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")
MEASURE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(centimetros?|centímetros?|cms?|milimetros?|milímetros?|mms?|metros?|mts?|m)\b", re.I)
SPLIT = re.compile(r"[a-z0-9_<>]+")
UNITS = {"c": 0.01, "m": 0.001}
MAX_LIT = 6
PAD, UNK, SEP, OUT, EOS = "<pad>", "<unk>", "<sep>", "<out>", "<eos>"
SPECIAL = (PAD, UNK, SEP, OUT, EOS)


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def hex_full(h: str) -> str:
    h = h.lower()
    return "#" + "".join(c * 2 for c in h[1:]) if len(h) == 4 else h


def prepare(text: str, extra_hex=()):
    """(palabras, colores_hex, medidas_m): los literales se sustituyen por <h0>.. y <n0>.. en orden de aparición."""
    hexes, nums = [], []

    def h(m):
        hexes.append(hex_full(m.group(0)))
        return f" <h{len(hexes) - 1}> " if len(hexes) <= MAX_LIT else " "

    def n(m):
        value = float(m.group(1).replace(",", "."))
        unit = m.group(2).lower()
        nums.append(value * (0.01 if unit.startswith("c") else 0.001 if unit.startswith("mi") or unit.startswith("mm") else 1.0))
        return f" <n{len(nums) - 1}> " if len(nums) <= MAX_LIT else " "

    text = HEX.sub(h, text)
    text = MEASURE.sub(n, text)
    words = SPLIT.findall(strip_accents(text.lower().replace("ñ", "n")))
    for c in extra_hex:                      # colores que vienen de una imagen adjunta, tras los del texto
        if len(hexes) < MAX_LIT:
            hexes.append(hex_full(c))
    return words, hexes[:MAX_LIT], nums[:MAX_LIT]


class Vocab:
    def __init__(self, tokens):
        self.itos = list(tokens)
        self.stoi = {t: i for i, t in enumerate(self.itos)}
        self._words = [t for t in self.itos if t.isalpha() and len(t) > 3]

    def id(self, token: str) -> int:
        return self.stoi.get(token, self.stoi[UNK])

    def word(self, w: str) -> int:
        """Id de una palabra; las que no conoce se acercan a la más parecida (erratas) o quedan como <unk>."""
        i = self.stoi.get(w)
        if i is not None:
            return i
        if len(w) > 3 and not w.isdigit():
            near = difflib.get_close_matches(w, self._words, n=1, cutoff=0.8)
            if near:
                return self.stoi[near[0]]
        return self.stoi[UNK]


def build_vocab(token_lists, extra=()) -> Vocab:
    seen = set()
    for t in token_lists:
        seen.update(t)
    seen.update(extra)
    return Vocab(list(SPECIAL) + sorted(seen - set(SPECIAL)))
