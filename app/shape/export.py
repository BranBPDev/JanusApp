import json
import struct
import numpy as np


def write_obj(path, V, F, N, name="objeto"):
    lines = [f"# JanusApp\no {name}"]
    lines += [f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in V]
    lines += [f"vn {x:.5f} {y:.5f} {z:.5f}" for x, y, z in N]
    lines += [f"f {a + 1}//{a + 1} {b + 1}//{b + 1} {c + 1}//{c + 1}" for a, b, c in F]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def _pad(data: bytes, byte: bytes) -> bytes:
    return data + byte * (-len(data) % 4)


def write_glb(path, V, F, N, name="objeto"):
    """glTF 2.0 binario (posiciones, normales e índices de 16 o 32 bits)."""
    pos = np.ascontiguousarray(V, "<f4").tobytes()
    nor = np.ascontiguousarray(N, "<f4").tobytes()
    idx_type = "<u2" if len(V) < 65536 else "<u4"
    idx = _pad(np.ascontiguousarray(F.reshape(-1), idx_type).tobytes(), b"\x00")
    blob = pos + nor + idx

    meta = {
        "asset": {"version": "2.0", "generator": "JanusApp"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": name}],
        "meshes": [{"name": name, "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 2, "mode": 4}]}],
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(pos), "target": 34962},
            {"buffer": 0, "byteOffset": len(pos), "byteLength": len(nor), "target": 34962},
            {"buffer": 0, "byteOffset": len(pos) + len(nor), "byteLength": len(idx), "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": len(V), "type": "VEC3",
             "min": V.min(axis=0).tolist(), "max": V.max(axis=0).tolist()},
            {"bufferView": 1, "componentType": 5126, "count": len(V), "type": "VEC3"},
            {"bufferView": 2, "componentType": 5123 if idx_type == "<u2" else 5125, "count": int(F.size), "type": "SCALAR"},
        ],
    }
    js = _pad(json.dumps(meta, separators=(",", ":")).encode(), b" ")
    total = 12 + 8 + len(js) + 8 + len(blob)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(blob), 0x004E4942) + blob)
