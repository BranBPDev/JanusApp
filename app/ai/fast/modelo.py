"""Transformer pequeño (solo decodificador, numpy puro): inferencia con caché de claves/valores y decodificación voraz restringida."""
import json
import math

import numpy as np

from app.ai.fast.texto import EOS, OUT, SEP, Vocab


def _ln(x, g, b):
    mu = x.mean(-1, keepdims=True)
    var = ((x - mu) ** 2).mean(-1, keepdims=True)
    return (x - mu) / np.sqrt(var + 1e-5) * g + b


def _gelu(u):
    return 0.5 * u * (1.0 + np.tanh(0.7978845608028654 * (u + 0.044715 * u ** 3)))


class FastModel:
    def __init__(self, path):
        z = np.load(path, allow_pickle=False)
        self.cfg = json.loads(str(z["cfg"]))
        self.vocab = Vocab(json.loads(str(z["vocab"])))
        self.out_ids = np.array(json.loads(str(z["out_ids"])), np.int64)      # fichas que puede escribir el programa
        self.w = {k: z[k].astype(np.float32) for k in z.files if k not in ("cfg", "vocab", "out_ids")}
        self.L, self.H, self.D = self.cfg["layers"], self.cfg["heads"], self.cfg["dim"]
        self.mask = np.full(len(self.vocab.itos), -1e9, np.float32)
        self.mask[self.out_ids] = 0.0

    def _forward(self, ids, cache, p0):
        """ids: fichas nuevas; cache: lista de (K, V) por capa. Devuelve los logits de la última."""
        w, H, D = self.w, self.H, self.D
        dh = D // H
        n = len(ids)
        x = w["E"][ids] + w["P"][p0:p0 + n]
        for l in range(self.L):
            h = _ln(x, w[f"l{l}.g1"], w[f"l{l}.b1"])
            qkv = h @ w[f"l{l}.Wqkv"] + w[f"l{l}.bqkv"]
            q, k, v = (qkv[:, i * D:(i + 1) * D].reshape(n, H, dh).transpose(1, 0, 2) for i in range(3))
            if cache[l] is None:
                cache[l] = [k, v]
            else:
                cache[l][0] = np.concatenate([cache[l][0], k], 1)
                cache[l][1] = np.concatenate([cache[l][1], v], 1)
            K, V = cache[l]
            s = q @ K.transpose(0, 2, 1) / math.sqrt(dh)
            if n > 1:
                t = K.shape[1]
                s = s + np.triu(np.full((n, t), -1e9, np.float32), 1 + t - n)
            s = np.exp(s - s.max(-1, keepdims=True))
            s /= s.sum(-1, keepdims=True)
            o = (s @ V).transpose(1, 0, 2).reshape(n, D)
            x = x + o @ w[f"l{l}.Wo"] + w[f"l{l}.bo"]
            h = _ln(x, w[f"l{l}.g2"], w[f"l{l}.b2"])
            x = x + _gelu(h @ w[f"l{l}.W1"] + w[f"l{l}.c1"]) @ w[f"l{l}.W2"] + w[f"l{l}.c2"]
        x = _ln(x[-1:], w["gf"], w["bf"])
        return (x @ w["E"].T)[0]

    def generate(self, ctx_tokens, words, max_new=60):
        """Programa (lista de fichas) para la petición; ctx_tokens = estado del objeto, words = palabras ya normalizadas."""
        v = self.vocab
        ids = [v.id(t) for t in ctx_tokens] + [v.stoi[SEP]] + [v.word(t) if not t.startswith("<") else v.id(t) for t in words][:120] + [v.stoi[OUT]]
        cache = [None] * self.L
        out, self.confidence = [], 1.0
        logits = self._forward(np.array(ids), cache, 0)
        pos = len(ids)
        for _ in range(max_new):
            z = logits + self.mask
            nxt = int(z.argmax())
            e = np.exp(z - z.max())
            self.confidence = min(self.confidence, float(e[nxt] / e.sum()))
            tok = v.itos[nxt]
            out.append(tok)
            if tok == "fin" or tok == EOS or pos >= self.cfg["ctx"] - 1:
                break
            logits = self._forward(np.array([nxt]), cache, pos)
            pos += 1
        return out
