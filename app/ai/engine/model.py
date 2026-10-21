"""Transformer tipo Qwen2/Qwen3 en numpy (CPU/RAM) con caché de claves/valores y reutilización del prefijo del prompt."""
import numpy as np

from app.ai.engine.gguf import GGUFFile


def _rms(x, w, eps):
    return x * (1.0 / np.sqrt(np.mean(x * x, axis=-1, keepdims=True) + eps)) * w


def _silu(x):
    return x / (1.0 + np.exp(-np.clip(x, -60, 60)))


class Layer:
    __slots__ = ("an", "wq", "wk", "wv", "bq", "bk", "bv", "wo", "qn", "kn", "fn", "wg", "wu", "wd")


class LlamaLike:
    """Soporta las arquitecturas «qwen2» y «qwen3» del formato GGUF."""

    def __init__(self, path, max_ctx=8192, progress=None):
        self.gguf = g = GGUFFile(path)
        m = self.meta = g.meta
        self.arch = str(m.get("general.architecture", ""))
        if self.arch not in ("qwen2", "qwen3"):
            raise ValueError(f"Arquitectura «{self.arch}» no soportada. Usa un modelo Qwen2.5 o Qwen3 en formato GGUF.")
        a = self.arch
        self.n_layers = int(m[f"{a}.block_count"])
        self.dim = int(m[f"{a}.embedding_length"])
        self.n_heads = int(m[f"{a}.attention.head_count"])
        self.n_kv = int(m.get(f"{a}.attention.head_count_kv", self.n_heads))
        self.head_dim = int(m.get(f"{a}.attention.key_length", self.dim // self.n_heads))
        self.eps = float(m.get(f"{a}.attention.layer_norm_rms_epsilon", 1e-6))
        self.theta = float(m.get(f"{a}.rope.freq_base", 10000.0))
        self.max_ctx = min(int(max_ctx), int(m.get(f"{a}.context_length", max_ctx)))
        self.vocab = None
        total = self.n_layers + 2
        step = [0]

        def tick():
            step[0] += 1
            if progress:
                progress(step[0] / total)

        t = g.tensor
        self.embed = t("token_embd.weight")
        self.vocab = self.embed.shape[0]
        self.out_norm = t("output_norm.weight")
        self.out_w = t("output.weight") if g.has("output.weight") else self.embed
        tick()
        self.layers = []
        for i in range(self.n_layers):
            L, p = Layer(), f"blk.{i}."
            L.an, L.fn = t(p + "attn_norm.weight"), t(p + "ffn_norm.weight")
            L.wq, L.wk, L.wv, L.wo = (t(p + f"attn_{n}.weight") for n in ("q", "k", "v", "output"))
            L.bq, L.bk, L.bv = (t(p + f"attn_{n}.bias") if g.has(p + f"attn_{n}.bias") else None for n in ("q", "k", "v"))
            L.qn = t(p + "attn_q_norm.weight") if g.has(p + "attn_q_norm.weight") else None
            L.kn = t(p + "attn_k_norm.weight") if g.has(p + "attn_k_norm.weight") else None
            L.wg, L.wu, L.wd = (t(p + f"ffn_{n}.weight") for n in ("gate", "up", "down"))
            self.layers.append(L)
            tick()
        inv = self.theta ** (-np.arange(0, self.head_dim, 2, dtype=np.float32) / self.head_dim)
        ang = np.arange(self.max_ctx, dtype=np.float32)[:, None] * inv[None, :]
        self.cos, self.sin = np.cos(ang).astype(np.float32), np.sin(ang).astype(np.float32)
        self.kc = np.zeros((self.n_layers, self.n_kv, self.max_ctx, self.head_dim), np.float32)
        self.vc = np.zeros_like(self.kc)
        self.cached = []                    # tokens cuya K/V están en la caché
        tick()
        g.close()

    # --- API ---
    def reset(self):
        self.cached = []

    def forward(self, tokens, n_out=1):
        """Procesa 'tokens' (lista completa del prompt/continuación); reutiliza el prefijo ya cacheado.
        Devuelve los logits del último token (vector) o, con n_out > 1, los de los últimos n_out (matriz)."""
        if len(tokens) >= self.max_ctx:
            raise ValueError("El texto no cabe en el contexto del modelo.")
        n = 0
        lim = min(len(tokens) - n_out, len(self.cached))      # siempre se recalculan al menos los n_out últimos tokens
        while n < lim and self.cached[n] == tokens[n]:
            n += 1
        del self.cached[n:]
        new = tokens[n:]
        out = None
        for s in range(0, len(new), 256):                 # trozos para limitar la memoria de las puntuaciones
            last = s + 256 >= len(new)
            out = self._step(new[s:s + 256], n + s, n_out if last else 0)
        self.cached = list(tokens)
        return out

    def _rope(self, x, pos0):
        """x: (T, H, hd) -> rotación NEOX."""
        T = x.shape[0]
        c, s = self.cos[pos0:pos0 + T][:, None, :], self.sin[pos0:pos0 + T][:, None, :]
        h = self.head_dim // 2
        x1, x2 = x[..., :h], x[..., h:]
        return np.concatenate([x1 * c - x2 * s, x2 * c + x1 * s], axis=-1)

    def _step(self, toks, p0, n_out=1):
        T = len(toks)
        hd, nh, nk = self.head_dim, self.n_heads, self.n_kv
        grp = nh // nk
        x = self.embed[np.asarray(toks)]
        S = p0 + T
        mask = None
        if T > 1:
            mask = np.where(np.arange(S)[None, :] > (p0 + np.arange(T))[:, None], -1e30, 0.0).astype(np.float32)
        scale = 1.0 / np.sqrt(hd)
        for li, L in enumerate(self.layers):
            h = _rms(x, L.an, self.eps)
            q, k, v = h @ L.wq.T, h @ L.wk.T, h @ L.wv.T
            if L.bq is not None:
                q, k, v = q + L.bq, k + L.bk, v + L.bv
            q, k, v = q.reshape(T, nh, hd), k.reshape(T, nk, hd), v.reshape(T, nk, hd)
            if L.qn is not None:
                q, k = _rms(q, L.qn, self.eps), _rms(k, L.kn, self.eps)
            q, k = self._rope(q, p0), self._rope(k, p0)
            self.kc[li, :, p0:S] = k.transpose(1, 0, 2)
            self.vc[li, :, p0:S] = v.transpose(1, 0, 2)
            qg = q.reshape(T, nk, grp, hd).transpose(1, 2, 0, 3).reshape(nk, grp * T, hd)
            sc = np.matmul(qg, self.kc[li, :, :S].transpose(0, 2, 1)) * scale          # (nk, grp*T, S)
            if mask is not None:
                sc = (sc.reshape(nk, grp, T, S) + mask).reshape(nk, grp * T, S)
            sc -= sc.max(-1, keepdims=True)
            np.exp(sc, out=sc)
            sc /= sc.sum(-1, keepdims=True)
            ctx = np.matmul(sc, self.vc[li, :, :S]).reshape(nk, grp, T, hd).transpose(2, 0, 1, 3).reshape(T, nh * hd)
            x = x + ctx @ L.wo.T
            h = _rms(x, L.fn, self.eps)
            x = x + (_silu(h @ L.wg.T) * (h @ L.wu.T)) @ L.wd.T
        if n_out == 0:
            return None
        rows = _rms(x[-n_out:], self.out_norm, self.eps)
        logits = rows @ self.out_w.T
        return logits[0] if n_out == 1 else logits
