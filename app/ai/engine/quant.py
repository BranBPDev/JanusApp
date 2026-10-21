"""Descuantización (vectorizada, numpy) de los formatos de tensor de GGUF -> float32.

Cada formato guarda los pesos en bloques con su escala; aquí se recorren todos los bloques a la vez. Soportados: F32, F16,
BF16, Q4_0, Q4_1, Q5_0, Q5_1, Q8_0 y los K-quants Q4_K, Q5_K y Q6_K (los de los archivos «Q4_K_M», «Q5_K_M» y «Q6_K»)."""
import numpy as np

F32, F16, Q4_0, Q4_1, Q5_0, Q5_1, Q8_0, Q4_K, Q5_K, Q6_K, BF16 = 0, 1, 2, 3, 6, 7, 8, 12, 13, 14, 30
QK = 32          # elementos por bloque en los formatos «clásicos»
QK_K = 256       # elementos por súper-bloque en los K-quants

# tipo -> (elementos por bloque, bytes por bloque)
LAYOUT = {F32: (1, 4), F16: (1, 2), BF16: (1, 2), Q4_0: (QK, 18), Q4_1: (QK, 20), Q5_0: (QK, 22), Q5_1: (QK, 24),
          Q8_0: (QK, 34), Q4_K: (QK_K, 144), Q5_K: (QK_K, 176), Q6_K: (QK_K, 210)}
NAMES = {F32: "F32", F16: "F16", BF16: "BF16", Q4_0: "Q4_0", Q4_1: "Q4_1", Q5_0: "Q5_0", Q5_1: "Q5_1", Q8_0: "Q8_0",
         Q4_K: "Q4_K", Q5_K: "Q5_K", Q6_K: "Q6_K"}


def nbytes(qtype: int, n_elements: int) -> int:
    if qtype not in LAYOUT:
        raise ValueError(f"Formato de tensor {qtype} no soportado. Usa un modelo en Q8_0, Q4_K_M, Q5_K_M, Q6_K, F16 o F32.")
    per, size = LAYOUT[qtype]
    if n_elements % per:
        raise ValueError("El número de elementos del tensor no es múltiplo del bloque.")
    return n_elements // per * size


def _f16(raw, offset):
    """float16 little endian en la columna 'offset' (2 bytes) de cada bloque -> (n,) float32."""
    return np.ascontiguousarray(raw[:, offset:offset + 2]).view("<f2").astype(np.float32).reshape(-1)


def _scale_min(scales):
    """Los 8 pares (escala, mínimo) de 6 bits de un súper-bloque K de 4/5 bits. scales: (n, 12) uint8 -> dos (n, 8)."""
    s = scales.astype(np.uint8)
    sc, mn = np.empty((len(s), 8), np.uint8), np.empty((len(s), 8), np.uint8)
    sc[:, :4], mn[:, :4] = s[:, 0:4] & 63, s[:, 4:8] & 63
    sc[:, 4:] = (s[:, 8:12] & 0x0F) | ((s[:, 0:4] >> 6) << 4)
    mn[:, 4:] = (s[:, 8:12] >> 4) | ((s[:, 4:8] >> 6) << 4)
    return sc.astype(np.float32), mn.astype(np.float32)


def dequantize(data, qtype: int, n_elements: int) -> np.ndarray:
    """Bytes de un tensor (buffer o array uint8) -> vector float32 de 'n_elements'."""
    buf = np.frombuffer(data, np.uint8, nbytes(qtype, n_elements))
    if qtype == F32:
        return buf.view("<f4").astype(np.float32)
    if qtype == F16:
        return buf.view("<f2").astype(np.float32)
    if qtype == BF16:
        return (buf.view("<u2").astype(np.uint32) << 16).view(np.float32)
    per, size = LAYOUT[qtype]
    raw = buf.reshape(-1, size)
    n = len(raw)
    if qtype == Q8_0:
        return (_f16(raw, 0)[:, None] * raw[:, 2:34].view(np.int8).astype(np.float32)).reshape(-1)
    if qtype in (Q4_0, Q4_1):
        head = 2 if qtype == Q4_0 else 4
        qs = raw[:, head:head + 16]
        q = np.concatenate([qs & 0x0F, qs >> 4], axis=1).astype(np.float32)
        d = _f16(raw, 0)[:, None]
        return ((q - 8.0) * d if qtype == Q4_0 else q * d + _f16(raw, 2)[:, None]).reshape(-1)
    if qtype in (Q5_0, Q5_1):
        head = 2 if qtype == Q5_0 else 4
        qh = np.ascontiguousarray(raw[:, head:head + 4]).view("<u4").reshape(-1)
        qs = raw[:, head + 4:head + 20]
        bit = ((qh[:, None] >> np.arange(32, dtype=np.uint32)) & 1).astype(np.uint8) << 4
        q = np.concatenate([qs & 0x0F, qs >> 4], axis=1) | bit
        d = _f16(raw, 0)[:, None]
        q = q.astype(np.float32)
        return ((q - 16.0) * d if qtype == Q5_0 else q * d + _f16(raw, 2)[:, None]).reshape(-1)
    if qtype == Q4_K:
        d, dmin = _f16(raw, 0)[:, None, None], _f16(raw, 2)[:, None, None]
        sc, mn = _scale_min(raw[:, 4:16])
        qs = raw[:, 16:144].reshape(n, 4, 32)
        lo, hi = (qs & 0x0F).astype(np.float32), (qs >> 4).astype(np.float32)   # (n, 4, 32): 4 trozos de 64
        sc, mn = sc.reshape(n, 4, 2), mn.reshape(n, 4, 2)
        out = np.stack([d * sc[:, :, 0:1] * lo - dmin * mn[:, :, 0:1], d * sc[:, :, 1:2] * hi - dmin * mn[:, :, 1:2]], axis=2)
        return out.reshape(-1)                               # (n, 4, [lo, hi], 32)
    if qtype == Q5_K:
        d, dmin = _f16(raw, 0)[:, None, None], _f16(raw, 2)[:, None, None]
        sc, mn = _scale_min(raw[:, 4:16])
        qh = raw[:, 16:48]                                   # (n, 32): un bit alto por elemento y trozo
        qs = raw[:, 48:176].reshape(n, 4, 32)
        shifts = (2 * np.arange(4)).astype(np.uint8)
        hb_lo = ((qh[:, None, :] >> shifts[None, :, None]) & 1).astype(np.float32) * 16.0
        hb_hi = ((qh[:, None, :] >> (shifts[None, :, None] + 1)) & 1).astype(np.float32) * 16.0
        lo, hi = (qs & 0x0F).astype(np.float32) + hb_lo, (qs >> 4).astype(np.float32) + hb_hi
        sc, mn = sc.reshape(n, 4, 2), mn.reshape(n, 4, 2)
        out = np.stack([d * sc[:, :, 0:1] * lo - dmin * mn[:, :, 0:1], d * sc[:, :, 1:2] * hi - dmin * mn[:, :, 1:2]], axis=2)
        return out.reshape(-1)
    if qtype == Q6_K:
        ql = raw[:, 0:128].reshape(n, 2, 2, 32)             # (n, mitad, [0:32 | 32:64], 32)
        qh = raw[:, 128:192].reshape(n, 2, 32)
        sc = raw[:, 192:208].view(np.int8).astype(np.float32).reshape(n, 2, 8)
        d = _f16(raw, 208)[:, None, None, None]
        q1 = (ql[:, :, 0] & 0x0F) | (((qh >> 0) & 3) << 4)
        q2 = (ql[:, :, 1] & 0x0F) | (((qh >> 2) & 3) << 4)
        q3 = (ql[:, :, 0] >> 4) | (((qh >> 4) & 3) << 4)
        q4 = (ql[:, :, 1] >> 4) | (((qh >> 6) & 3) << 4)
        q = np.stack([q1, q2, q3, q4], axis=2).astype(np.float32) - 32.0      # (n, mitad, 4, 32)
        scale = np.repeat(sc.reshape(n, 2, 4, 2), 16, axis=3)                 # escala de cada grupo de 16 elementos
        return (d * scale * q).reshape(-1)
    raise ValueError(f"Formato de tensor {qtype} no soportado.")
