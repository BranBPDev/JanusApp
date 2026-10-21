"""Tokenizador BPE a nivel de bytes (estilo GPT-2/Qwen) leído de los metadatos del GGUF, sin dependencias."""
import re

# Preseparación de Qwen2/Qwen3 (\p{L} ≈ letra, \p{N} ≈ dígito), con «re» estándar.
_PRE = re.compile(
    r"(?i:'s|'t|'re|'ve|'m|'ll|'d)"
    r"|(?:[^\r\n\w]|_)?[^\W\d_]+"
    r"|\d"
    r"| ?(?:[^\s\w]|_)+[\r\n]*"
    r"|\s*[\r\n]+"
    r"|\s+(?!\S)"
    r"|\s+")


def _byte_maps():
    keep = list(range(33, 127)) + list(range(161, 173)) + list(range(174, 256))
    chars, n = {}, 0
    for b in range(256):
        if b in keep:
            chars[b] = chr(b)
        else:
            chars[b] = chr(256 + n)
            n += 1
    return chars, {c: b for b, c in chars.items()}


BYTE2CHAR, CHAR2BYTE = _byte_maps()


class Tokenizer:
    def __init__(self, meta: dict):
        self.tokens = [str(t) for t in meta["tokenizer.ggml.tokens"]]
        self.index = {t: i for i, t in enumerate(self.tokens)}
        merges = meta.get("tokenizer.ggml.merges") or []
        self.rank = {tuple(m.split(" ", 1)): i for i, m in enumerate(merges)}
        types = meta.get("tokenizer.ggml.token_type")
        self.special = {}
        for i, t in enumerate(self.tokens):
            ty = int(types[i]) if types is not None else 1
            if ty in (3, 4) and len(t) > 2 and t[0] == "<" and t[-1] == ">":
                self.special[t] = i
        self.eos = int(meta.get("tokenizer.ggml.eos_token_id", -1))
        self.bos = meta.get("tokenizer.ggml.bos_token_id")
        self.end_ids = {i for t, i in self.special.items() if t in ("<|im_end|>", "<|endoftext|>", "<|eot_id|>")} | {self.eos}
        self._special_re = re.compile("(" + "|".join(re.escape(t) for t in sorted(self.special, key=len, reverse=True)) + ")") if self.special else None
        self._cache = {}
        self._bytes = {}
        self._text = [self._piece_text(i) for i in range(len(self.tokens))]

    def _piece_text(self, i):
        t = self.tokens[i]
        if t in self.special:
            return ""
        return bytes(CHAR2BYTE.get(c, 63) for c in t).decode("utf-8", errors="ignore")

    def _bpe(self, word: str):
        hit = self._cache.get(word)
        if hit is not None:
            return hit
        parts = list(word)
        while len(parts) > 1:
            best, at = None, -1
            for i in range(len(parts) - 1):
                r = self.rank.get((parts[i], parts[i + 1]))
                if r is not None and (best is None or r < best):
                    best, at = r, i
            if best is None:
                break
            parts[at:at + 2] = [parts[at] + parts[at + 1]]
        ids = [self.index[p] for p in parts if p in self.index]
        if len(self._cache) < 50000:
            self._cache[word] = ids
        return ids

    def encode(self, text: str):
        ids = []
        chunks = self._special_re.split(text) if self._special_re else [text]
        for chunk in chunks:
            if not chunk:
                continue
            if chunk in self.special:
                ids.append(self.special[chunk])
                continue
            for m in _PRE.finditer(chunk):
                word = "".join(BYTE2CHAR[b] for b in m.group().encode("utf-8"))
                ids.extend(self._bpe(word))
        return ids

    def piece(self, i: int) -> bytes:
        """Bytes crudos de un token (los especiales no producen texto)."""
        b = self._bytes.get(i)
        if b is None:
            t = self.tokens[i]
            b = self._bytes[i] = b"" if t in self.special else bytes(CHAR2BYTE.get(c, 63) for c in t)
        return b

    def decode(self, ids) -> str:
        return b"".join(self.piece(i) for i in ids).decode("utf-8", errors="replace")

    def text_of(self, i: int) -> str:
        """Texto aproximado de un token (para comprobar candidatos del JSON); los especiales -> ''."""
        return self._text[i]
