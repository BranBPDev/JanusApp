import io
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image


def texture_png(texture: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(texture, "RGBA").save(buf, "PNG", optimize=True)
    return buf.getvalue()


def write_obj(path, model, name="objeto"):
    """OBJ en pose de reposo (grupos por pieza) + .mtl. La textura se guarda aparte como texture.png."""
    path = Path(path)
    mtl = path.with_suffix(".mtl")
    lines = [f"mtllib {mtl.name}", f"o {name}"]
    has_uv = model.parts[0].uvs is not None
    v, vt, vn, faces, off = [], [], [], [], 0
    for p in model.parts:
        v += [f"v {x:.5f} {y:.5f} {z:.5f}" for x, y, z in p.vertices]
        vn += [f"vn {x:.4f} {y:.4f} {z:.4f}" for x, y, z in p.normals]
        if has_uv:
            vt += [f"vt {a:.5f} {1 - b:.5f}" for a, b in p.uvs]  # OBJ tiene el origen de v abajo
        faces.append(f"g {p.name}")
        for a, b, c in p.faces + off + 1:
            faces.append(f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}" if has_uv else f"f {a}//{a} {b}//{b} {c}//{c}")
        off += len(p.vertices)
    lines += ["usemtl janus"] + v + vt + vn + faces
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    mtl.write_text("newmtl janus\nKd 1 1 1\n" + ("map_Kd texture.png\n" if model.texture is not None else ""), encoding="utf-8")


def _pad(data: bytes, byte: bytes = b"\x00") -> bytes:
    return data + byte * (-len(data) % 4)


def write_glb(path, model, name="objeto"):
    """glTF 2.0 binario: una malla por pieza, jerarquía de nodos con pivotes y una sola textura/material."""
    buf = bytearray()
    views, accessors, meshes, nodes = [], [], [], [{"name": name, "children": []}]

    def add_view(data: bytes, target=None):
        views.append({"buffer": 0, "byteOffset": len(buf), "byteLength": len(data), **({"target": target} if target else {})})
        buf.extend(_pad(data))
        return len(views) - 1

    def add_acc(data: bytes, target, ctype, count, kind, **extra):
        accessors.append({"bufferView": add_view(data, target), "componentType": ctype, "count": count, "type": kind, **extra})
        return len(accessors) - 1

    origins = {p.name: np.array(p.origin) for p in model.parts}
    node_of = {}
    for p in model.parts:
        local = (p.vertices - np.array(p.origin, np.float32)).astype("<f4")
        attrs = {"POSITION": add_acc(local.tobytes(), 34962, 5126, len(local), "VEC3",
                                     min=local.min(axis=0).tolist(), max=local.max(axis=0).tolist()),
                 "NORMAL": add_acc(np.ascontiguousarray(p.normals, "<f4").tobytes(), 34962, 5126, len(local), "VEC3")}
        if p.uvs is not None:
            attrs["TEXCOORD_0"] = add_acc(np.ascontiguousarray(p.uvs, "<f4").tobytes(), 34962, 5126, len(local), "VEC2")
        small = len(local) < 65536
        idx = add_acc(np.ascontiguousarray(p.faces.reshape(-1), "<u2" if small else "<u4").tobytes(), 34963,
                      5123 if small else 5125, int(p.faces.size), "SCALAR")
        prim = {"attributes": attrs, "indices": idx, "mode": 4}
        if model.texture is not None:
            prim["material"] = 0
        meshes.append({"name": p.name, "primitives": [prim]})

        node = {"name": p.name, "mesh": len(meshes) - 1}
        parent_origin = origins[p.parent] if p.parent else np.zeros(3)
        t = (origins[p.name] - parent_origin).tolist()
        if any(abs(c) > 1e-9 for c in t):
            node["translation"] = t
        if p.axis is not None:
            node["extras"] = {"janus": {"axis": list(p.axis), "open_angle_deg": p.open_angle}}
        nodes.append(node)
        node_of[p.name] = len(nodes) - 1
    for p in model.parts:
        parent = nodes[node_of[p.parent]] if p.parent else nodes[0]
        parent.setdefault("children", []).append(node_of[p.name])

    meta = {
        "asset": {"version": "2.0", "generator": "JanusApp"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": nodes, "meshes": meshes,
        "accessors": accessors,
    }
    if model.texture is not None:
        image_view = add_view(texture_png(model.texture))
        meta.update({
            "images": [{"bufferView": image_view, "mimeType": "image/png"}],
            "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 33071}],
            "textures": [{"sampler": 0, "source": 0}],
            "materials": [{"name": "janus", "pbrMetallicRoughness": {
                "baseColorTexture": {"index": 0}, "metallicFactor": 0.0, "roughnessFactor": 0.5}}],
        })
    meta.update({"bufferViews": views, "buffers": [{"byteLength": len(buf)}]})

    js = _pad(json.dumps(meta, separators=(",", ":")).encode(), b" ")
    blob = bytes(buf)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(blob), 0x004E4942) + blob)
