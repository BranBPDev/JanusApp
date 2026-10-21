"""Lector de archivos GGUF (v2/v3) en Python puro: metadatos + tensores (mapeados en memoria, descuantizados al pedirlos)."""
import mmap
import struct

import numpy as np

from app.ai.engine import quant

MAGIC = b"GGUF"
_SCALAR = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}
STRING, ARRAY = 8, 9


class _Reader:
    def __init__(self, buf):
        self.buf, self.pos = buf, 0

    def unpack(self, fmt):
        size = struct.calcsize(fmt)
        value = struct.unpack_from(fmt, self.buf, self.pos)[0]
        self.pos += size
        return value

    def string(self):
        n = self.unpack("<Q")
        s = bytes(self.buf[self.pos:self.pos + n]).decode("utf-8", errors="replace")
        self.pos += n
        return s

    def value(self, vtype):
        if vtype == STRING:
            return self.string()
        if vtype == ARRAY:
            etype, n = self.unpack("<I"), self.unpack("<Q")
            if etype in _SCALAR:                                     # arrays numéricos: lectura en bloque
                dt = np.dtype(_SCALAR[etype])
                arr = np.frombuffer(self.buf, dt, n, self.pos).copy()
                self.pos += n * dt.itemsize
                return arr
            return [self.value(etype) for _ in range(n)]
        if vtype in _SCALAR:
            return self.unpack(_SCALAR[vtype])
        raise ValueError(f"Tipo de metadato GGUF desconocido: {vtype}")


class GGUFFile:
    """meta: dict clave->valor; tensors: nombre -> (shape numpy, qtype, offset absoluto)."""

    def __init__(self, path):
        self._fh = open(path, "rb")
        self.buf = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ)
        if bytes(self.buf[:4]) != MAGIC:
            raise ValueError("El archivo no es un modelo GGUF.")
        r = _Reader(self.buf)
        r.pos = 4
        self.version = r.unpack("<I")
        if self.version not in (2, 3):
            raise ValueError(f"Versión de GGUF no soportada: {self.version}")
        n_tensors, n_kv = r.unpack("<Q"), r.unpack("<Q")
        self.meta = {}
        for _ in range(n_kv):
            key = r.string()
            self.meta[key] = r.value(r.unpack("<I"))
        infos = []
        for _ in range(n_tensors):
            name = r.string()
            nd = r.unpack("<I")
            dims = [r.unpack("<Q") for _ in range(nd)]
            qtype, off = r.unpack("<I"), r.unpack("<Q")
            infos.append((name, tuple(reversed(dims)), qtype, off))     # GGUF guarda las dimensiones al revés
        align = int(self.meta.get("general.alignment", 32))
        base = (r.pos + align - 1) // align * align
        self.tensors = {n: (shape, q, base + off) for n, shape, q, off in infos}

    def has(self, name):
        return name in self.tensors

    def tensor(self, name) -> np.ndarray:
        """Tensor completo descuantizado a float32 con su forma."""
        shape, qtype, off = self.tensors[name]
        n = int(np.prod(shape)) if shape else 1
        return quant.dequantize(self.buf[off:off + quant.nbytes(qtype, n)], qtype, n).reshape(shape)

    def raw(self, name):
        """(shape, qtype, bytes uint8) sin descuantizar, para mantener los pesos grandes comprimidos en RAM."""
        shape, qtype, off = self.tensors[name]
        n = int(np.prod(shape)) if shape else 1
        return shape, qtype, np.frombuffer(self.buf, np.uint8, quant.nbytes(qtype, n), off)

    def close(self):
        try:
            self.buf.close()
            self._fh.close()
        except Exception:
            pass


# ---- escritor mínimo (solo para las pruebas con un modelo sintético) ----
def write_gguf(path, meta: dict, tensors: dict, align=32):
    """meta: str->(tipo,valor) con tipo en {'u32','f32','str','arr_str','arr_f32','arr_i32'}; tensors: nombre->(array float32, qtype)."""
    def s(x):
        b = x.encode()
        return struct.pack("<Q", len(b)) + b
    out = [MAGIC, struct.pack("<IQQ", 3, len(tensors), len(meta))]
    codes = {"u32": 4, "f32": 6, "str": 8, "i32": 5}
    for k, (t, v) in meta.items():
        out.append(s(k))
        if t in ("u32", "f32", "i32"):
            out += [struct.pack("<I", codes[t]), struct.pack({"u32": "<I", "f32": "<f", "i32": "<i"}[t], v)]
        elif t == "str":
            out += [struct.pack("<I", 8), s(v)]
        elif t == "arr_str":
            out += [struct.pack("<I", 9), struct.pack("<IQ", 8, len(v))] + [s(x) for x in v]
        elif t == "arr_f32":
            out += [struct.pack("<I", 9), struct.pack("<IQ", 6, len(v)), np.asarray(v, "<f4").tobytes()]
        elif t == "arr_i32":
            out += [struct.pack("<I", 9), struct.pack("<IQ", 5, len(v)), np.asarray(v, "<i4").tobytes()]
    blobs, off = [], 0
    for name, (arr, qtype) in tensors.items():
        data = _encode(arr, qtype)
        out += [s(name), struct.pack("<I", arr.ndim), b"".join(struct.pack("<Q", d) for d in reversed(arr.shape)),
                struct.pack("<IQ", qtype, off)]
        pad = (-len(data)) % align
        blobs.append(data + b"\0" * pad)
        off += len(data) + pad
    head = b"".join(out)
    head += b"\0" * ((-len(head)) % align)
    with open(path, "wb") as f:
        f.write(head + b"".join(blobs))


def _encode(arr, qtype):
    a = np.ascontiguousarray(arr, np.float32)
    if qtype == quant.F32:
        return a.astype("<f4").tobytes()
    if qtype == quant.F16:
        return a.astype("<f2").tobytes()
    if qtype == quant.Q8_0:
        blk = a.reshape(-1, 32)
        d = np.abs(blk).max(1) / 127.0
        d[d == 0] = 1.0
        q = np.rint(blk / d[:, None]).astype(np.int8)
        out = np.empty((len(blk), 34), np.uint8)
        out[:, :2] = d.astype("<f2").view(np.uint8).reshape(-1, 2)
        out[:, 2:] = q.view(np.uint8)
        return out.tobytes()
    if qtype == quant.Q4_0:
        blk = a.reshape(-1, 32)
        d = np.abs(blk).max(1) / 7.0
        d[d == 0] = 1.0
        q = np.clip(np.rint(blk / d[:, None]) + 8, 0, 15).astype(np.uint8)
        out = np.empty((len(blk), 18), np.uint8)
        out[:, :2] = d.astype("<f2").view(np.uint8).reshape(-1, 2)
        out[:, 2:] = q[:, :16] | (q[:, 16:] << 4)
        return out.tobytes()
    raise ValueError("Formato no soportado por el escritor de pruebas")
