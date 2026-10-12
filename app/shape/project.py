import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.shape.export import texture_png, write_glb, write_obj
from app.shape.naming import IMAGE_SUFFIXES
from app.shape.pipeline import ShapeResult
from app.utils.json_util import read_json, save_json
from app.utils.paths_util import PROJECTS_DIR

PHASES = ("shape", "texture", "collision", "rig")
MANIFEST = "manifest.json"
# Entradas de un proyecto: carpeta dentro del proyecto y clave del manifest.
INPUT_FOLDERS = {"views": "views", "grids": "grids", "interiors": "interiors"}


def sanitize_name(name: str) -> str:
    return re.sub(r"[^\w\-. ]", "_", name).strip(" .")[:60]


def project_dir(name: str) -> Path:
    return PROJECTS_DIR / sanitize_name(name)


def _read_manifest(root: Path) -> dict:
    try:
        return read_json(root / MANIFEST)
    except Exception:
        return {}


def _copy_inputs(root: Path, folder: str, paths: Optional[dict]) -> dict:
    """Copia las imágenes de entrada a <proyecto>/<folder>/<clave>.<ext> y devuelve {clave: ruta relativa}."""
    saved = {}
    for key, src in (paths or {}).items():
        if not src:
            continue
        src = Path(src)
        dest = root / folder / f"{key}{src.suffix.lower()}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dest.resolve():
            shutil.copyfile(src, dest)
        saved[key] = f"{folder}/{dest.name}"
    return saved


def save_shape(name: str, view_paths: dict, grid_paths: dict, result: ShapeResult, interior_paths: dict = None) -> Path:
    """Guarda vistas, mallas, texturas interiores, un GLB por LOD, el OBJ/MTL/textura del LOD0 y manifest.json
    (conserva las demás fases). Las esferas/elipsoides también se exportan como GLB ya cortado."""
    root = project_dir(name)
    shape_dir = root / "shape"
    shape_dir.mkdir(parents=True, exist_ok=True)

    saved = {k: _copy_inputs(root, folder, paths)
             for k, folder, paths in (("views", "views", view_paths), ("grids", "grids", grid_paths),
                                      ("interiors", "interiors", interior_paths))}

    for old in shape_dir.iterdir():
        old.unlink()
    lods = []
    for i, model in enumerate(result.lods):
        write_glb(shape_dir / f"lod{i}.glb", model, name)
        lods.append({"level": i, "glb": f"shape/lod{i}.glb", "triangles": model.triangles,
                     "vertices": model.vertex_count})
    lod0 = result.lods[0]
    write_obj(shape_dir / "lod0.obj", lod0, name)
    if lod0.texture is not None:
        (shape_dir / "texture.png").write_bytes(texture_png(lod0.texture))
    parts = [{"name": p.name, "parent": p.parent, "origin": list(p.origin), "axis": list(p.axis) if p.axis else None,
              "open_angle_deg": p.open_angle} for p in lod0.parts]

    manifest = _read_manifest(root)
    phases = manifest.get("phases", {})
    manifest.update({
        "name": name,
        "updated": datetime.now().isoformat(timespec="seconds"),
        "views": saved["views"],
        "grids": saved["grids"],
        "interiors": saved["interiors"],
        "annotations": result.marks,
        "shape": {"parts": parts, "lods": lods, "primitive_object": result.descriptor, **result.info},
        "phases": {p: bool(phases.get(p, False)) for p in PHASES} | {"shape": True, "texture": lod0.texture is not None},
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
    thumbnail: Optional[Path] = None


def _first_image(root: Path, rels: dict) -> Optional[Path]:
    for key in ("front", *rels):
        rel = rels.get(key)
        if rel and (root / rel).is_file():
            return root / rel
    return None


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
                openable=bool(shape.get("openable")), thumbnail=_first_image(root, manifest.get("views", {}))))
    return sorted(found, key=lambda p: p.updated, reverse=True)


def load_project_inputs(name: str) -> dict:
    """Rutas absolutas (solo las que existen) de las vistas, mallas y texturas interiores de un proyecto."""
    root = project_dir(name)
    manifest = _read_manifest(root)
    return {key: {k: str(root / rel) for k, rel in manifest.get(key, {}).items()
                  if (root / rel).suffix.lower() in IMAGE_SUFFIXES and (root / rel).is_file()}
            for key in INPUT_FOLDERS}
