import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from app.shape.pipeline import ShapeResult
from app.shape.rig.skeleton import Skeleton, attach_skeleton
from app.shape.storage.export import read_obj, texture_png, write_glb, write_obj
from app.utils.json_util import read_json, save_json
from app.utils.paths_util import PROJECTS_DIR
from app.utils.pool_util import parallel_map

PHASES = ("shape", "texture", "collision", "rig")
MANIFEST = "manifest.json"
SOURCE = "source/objeto.json"   # el JSON del objeto: lo único que hace falta para regenerarlo


def sanitize_name(name: str) -> str:
    return re.sub(r"[^\w\-. ]", "_", name).strip(" .")[:60]


def project_dir(name: str) -> Path:
    return PROJECTS_DIR / sanitize_name(name)


def _read_manifest(root: Path) -> dict:
    try:
        return read_json(root / MANIFEST)
    except Exception:
        return {}


def save_shape(name: str, result: ShapeResult, source_text: str = None) -> Path:
    """Guarda el JSON de origen, un GLB por LOD, el OBJ/MTL/textura del LOD0 y manifest.json (conserva las demás fases).
    Las esferas/elipsoides también se exportan como GLB ya cortado."""
    root = project_dir(name)
    shape_dir = root / "shape"
    shape_dir.mkdir(parents=True, exist_ok=True)
    if source_text is not None:
        (root / SOURCE).parent.mkdir(parents=True, exist_ok=True)
        (root / SOURCE).write_text(source_text, encoding="utf-8")

    for old in shape_dir.iterdir():
        old.unlink()
    write_glb_levels = lambda item: write_glb(shape_dir / f"lod{item[0]}.glb", item[1], name)
    parallel_map(write_glb_levels, enumerate(result.lods))          # los LOD son independientes: se escriben a la vez
    lods = [{"level": i, "glb": f"shape/lod{i}.glb", "triangles": m.triangles, "vertices": m.vertex_count}
            for i, m in enumerate(result.lods)]
    lod0 = result.lods[0]
    write_obj(shape_dir / "lod0.obj", lod0, name)
    if lod0.texture is not None:
        (shape_dir / "texture.png").write_bytes(texture_png(lod0.texture))
    parts = [{"name": p.name, "parent": p.parent, "origin": list(p.origin), "axis": list(p.axis) if p.axis else None,
              "open_angle_deg": p.open_angle} for p in lod0.parts]

    manifest = _read_manifest(root)
    for stale in ("views", "grids", "interiors"):      # entradas de proyectos antiguos (hechos con imágenes)
        manifest.pop(stale, None)
    phases = manifest.get("phases", {})
    manifest.update({
        "name": name,
        "updated": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE if source_text is not None else manifest.get("source"),
        "annotations": result.marks,
        "shape": {"parts": parts, "lods": lods, "primitive_object": result.descriptor, **result.info,
                  "skeleton": None if lod0.skeleton is None else lod0.skeleton.to_dict()},
        "phases": {p: bool(phases.get(p, False)) for p in PHASES} | {"shape": True, "texture": lod0.texture is not None,
                                                                      "rig": lod0.skeleton is not None},
    })
    save_json(root / MANIFEST, manifest)
    return root


# ---------- Consulta de proyectos existentes ----------
@dataclass
class ProjectInfo:
    name: str
    root: Path
    updated: str = ""
    triangles: int = 0
    openable: bool = False


def list_projects() -> list:
    """Proyectos guardados en local (los que tienen manifest.json), del más reciente al más antiguo."""
    found = []
    if PROJECTS_DIR.is_dir():
        for root in PROJECTS_DIR.iterdir():
            manifest = _read_manifest(root) if root.is_dir() else {}
            if not manifest:
                continue
            shape = manifest.get("shape", {})
            tri = shape.get("triangles") or [0]
            found.append(ProjectInfo(
                name=manifest.get("name") or root.name, root=root, updated=manifest.get("updated", ""),
                triangles=int(tri[0]) if isinstance(tri, list) else int(tri),
                openable=bool(shape.get("openable"))))
    return sorted(found, key=lambda p: p.updated, reverse=True)


def load_project_source(name: str):
    """Texto del JSON con el que se generó el proyecto, o None si no lo tiene (proyectos hechos con imágenes)."""
    file = project_dir(name) / SOURCE
    return file.read_text(encoding="utf-8") if file.is_file() else None


def load_model(root: Path):
    """Reconstruye el modelo guardado (LOD0: OBJ + textura + jerarquía del manifest) o None si no se puede leer."""
    try:
        texture_file = root / "shape" / "texture.png"
        texture = np.asarray(Image.open(texture_file).convert("RGBA"), np.uint8) if texture_file.is_file() else None
        model = read_obj(root / "shape" / "lod0.obj", texture)
        info = {p["name"]: p for p in _read_manifest(root).get("shape", {}).get("parts", [])}
        for part in model.parts:
            extra = info.get(part.name)
            if extra:
                part.parent, part.origin = extra.get("parent"), tuple(extra.get("origin", (0.0, 0.0, 0.0)))
                part.axis = tuple(extra["axis"]) if extra.get("axis") else None
                part.open_angle = extra.get("open_angle_deg", 0.0)
        skeleton = _read_manifest(root).get("shape", {}).get("skeleton")
        if skeleton:
            attach_skeleton(model, Skeleton.from_dict(skeleton))
        return model
    except Exception:
        return None
