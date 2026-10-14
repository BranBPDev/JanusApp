import io
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image

from app.shape.model import Model, Part
from app.shape.skeleton import swing_pose


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


def read_obj(path, texture=None) -> Model:
    """Lee el OBJ escrito por write_obj (pose de reposo, un grupo por pieza) y devuelve un Model.
    Las propiedades de la jerarquía (parent, origin, axis, open_angle) no van en el OBJ: las añade quien lo llama."""
    v, vt, vn, groups = [], [], [], {}
    cur = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        tag, _, rest = line.partition(" ")
        if tag == "v":
            v.append([float(x) for x in rest.split()])
        elif tag == "vt":
            u, w = rest.split()[:2]
            vt.append([float(u), 1.0 - float(w)])   # el OBJ tiene el origen de v abajo
        elif tag == "vn":
            vn.append([float(x) for x in rest.split()])
        elif tag == "g":
            cur = groups.setdefault(rest.strip(), [])
        elif tag == "f" and cur is not None:
            cur.append([int(c.split("/")[0]) - 1 for c in rest.split()])
    V, VT, VN = np.array(v, np.float32), np.array(vt, np.float32), np.array(vn, np.float32)
    parts = []
    for name, faces in groups.items():
        F = np.array(faces, np.int32)
        used = np.unique(F)
        remap = np.zeros(len(V), np.int32)
        remap[used] = np.arange(len(used))
        parts.append(Part(name, V[used], remap[F], VN[used], VT[used] if len(VT) == len(V) else None))
    return Model(parts, texture)


def _pad(data: bytes, byte: bytes = b"\x00") -> bytes:
    return data + byte * (-len(data) % 4)


ANIMATION = {"name": "demo_movimiento", "seconds": 2.0, "frames": 24}


def _quaternion(axis, angle):
    a = np.asarray(axis, np.float64)
    a = a / max(np.linalg.norm(a), 1e-12)
    return [*(a * np.sin(angle / 2)).tolist(), float(np.cos(angle / 2))]


def write_glb(path, model, name="objeto", animation=True):
    """glTF 2.0 binario: una malla por pieza, jerarquía de nodos con pivotes y una sola textura/material.
    Si el modelo tiene esqueleto: un nodo por hueso, 'skin' con sus matrices inversas, JOINTS_0/WEIGHTS_0 en las piezas
    (con los vértices en reposo, sin pivote) y, si 'animation', un movimiento de prueba genérico."""
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
    sk = model.skeleton
    joint_node = []
    if sk is not None:                          # huesos: nodos con la posición local respecto al padre
        for i, bone in enumerate(sk.names):
            parent = sk.parents[i]
            t = (sk.rest[i] - (sk.rest[parent] if parent >= 0 else 0.0))
            nodes.append({"name": bone, "translation": [float(v) for v in t]})
            joint_node.append(len(nodes) - 1)
        for i, parent in enumerate(sk.parents):
            host = nodes[0] if parent < 0 else nodes[joint_node[parent]]
            host.setdefault("children", []).append(joint_node[i])
    skinned = sk is not None
    for p in model.parts:
        rigged = skinned and p.joints is not None
        local = (p.vertices if rigged else p.vertices - np.array(p.origin, np.float32)).astype("<f4")
        attrs = {"POSITION": add_acc(local.tobytes(), 34962, 5126, len(local), "VEC3",
                                     min=local.min(axis=0).tolist(), max=local.max(axis=0).tolist()),
                 "NORMAL": add_acc(np.ascontiguousarray(p.normals, "<f4").tobytes(), 34962, 5126, len(local), "VEC3")}
        if rigged:
            attrs["JOINTS_0"] = add_acc(np.ascontiguousarray(p.joints, "u1").tobytes(), 34962, 5121, len(local), "VEC4")
            attrs["WEIGHTS_0"] = add_acc(np.ascontiguousarray(p.weights, "<f4").tobytes(), 34962, 5126, len(local), "VEC4")
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
        if rigged:
            node["skin"] = 0
        else:
            parent_origin = origins[p.parent] if p.parent else np.zeros(3)
            t = (origins[p.name] - parent_origin).tolist()
            if any(abs(c) > 1e-9 for c in t):
                node["translation"] = t
        if p.axis is not None:
            node["extras"] = {"janus": {"axis": list(p.axis), "open_angle_deg": p.open_angle}}
        nodes.append(node)
        node_of[p.name] = len(nodes) - 1
    for p in model.parts:
        rigged = skinned and p.joints is not None
        parent = nodes[node_of[p.parent]] if p.parent and not rigged else nodes[0]
        parent.setdefault("children", []).append(node_of[p.name])

    meta = {
        "asset": {"version": "2.0", "generator": "JanusApp"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": nodes, "meshes": meshes,
        "accessors": accessors,
    }
    if skinned:
        ibm = np.tile(np.eye(4, dtype="<f4"), (len(sk), 1, 1))
        ibm[:, 3, :3] = -np.asarray(sk.rest, np.float32)        # glTF guarda las matrices por columnas
        skin = {"joints": joint_node, "skeleton": joint_node[0],
                "inverseBindMatrices": add_acc(ibm.astype("<f4").tobytes(), None, 5126, len(sk), "MAT4")}
        meta["skins"] = [skin]
        if animation:
            n = ANIMATION["frames"]
            phases = np.arange(n + 1) / n * 2 * np.pi
            times = (np.arange(n + 1) / n * ANIMATION["seconds"]).astype("<f4")
            t_acc = add_acc(times.tobytes(), None, 5126, n + 1, "SCALAR", min=[0.0], max=[float(times[-1])])
            samplers, channels = [], []
            tracks = [swing_pose(sk, ph) for ph in phases]
            for i in range(1, len(sk)):
                axis = tracks[0][0][i]
                angles = [tr[1][i] for tr in tracks]
                if max(abs(a) for a in angles) < 1e-6:
                    continue
                quats = np.array([_quaternion(axis, a) for a in angles], "<f4")
                samplers.append({"input": t_acc, "output": add_acc(quats.tobytes(), None, 5126, n + 1, "VEC4"),
                                 "interpolation": "LINEAR"})
                channels.append({"sampler": len(samplers) - 1, "target": {"node": joint_node[i], "path": "rotation"}})
            if channels:
                meta["animations"] = [{"name": ANIMATION["name"], "samplers": samplers, "channels": channels}]
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
