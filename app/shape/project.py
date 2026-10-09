import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from app.shape.export import texture_png, write_glb, write_obj
from app.shape.pipeline import ShapeParams, ShapeResult
from app.utils.paths_util import PROJECTS_DIR

PHASES = ("shape", "texture", "collision", "rig")


def sanitize_name(name: str) -> str:
    return re.sub(r"[^\w\-. ]", "_", name).strip(" .")[:60]


def project_dir(name: str) -> Path:
    return PROJECTS_DIR / sanitize_name(name)


def save_shape(name: str, view_paths: dict, params: ShapeParams, result: ShapeResult) -> Path:
    """Guarda vistas, un GLB por LOD, el OBJ/MTL/textura del LOD0 y manifest.json (conserva las demás fases)."""
    root = project_dir(name)
    views_dir, shape_dir = root / "views", root / "shape"
    views_dir.mkdir(parents=True, exist_ok=True)
    shape_dir.mkdir(parents=True, exist_ok=True)

    views = {}
    for key, src in view_paths.items():
        if not src:
            continue
        src = Path(src)
        dest = views_dir / f"{key}{src.suffix.lower()}"
        if src.resolve() != dest.resolve():
            shutil.copyfile(src, dest)
        views[key] = f"views/{dest.name}"

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

    manifest_path = root / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
    phases = manifest.get("phases", {})
    manifest.update({
        "name": name,
        "updated": datetime.now().isoformat(timespec="seconds"),
        "views": views,
        "shape": {"parts": parts, "lods": lods, "params": vars(params), **result.info},
        "phases": {p: bool(phases.get(p, False)) for p in PHASES} | {"shape": True, "texture": lod0.texture is not None},
    })
    manifest_path.write_text(json.dumps(manifest, indent=4, ensure_ascii=False), encoding="utf-8")
    return root
