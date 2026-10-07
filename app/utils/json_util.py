import json
from pathlib import Path
from typing import Union


def parse_json(raw: Union[bytes, str]) -> dict:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")  # tolera BOM
    return json.loads(raw)


def read_json(file_path: Path) -> dict:
    if not file_path.exists():
        raise FileNotFoundError(f"JSON no encontrado: {file_path}")
    return parse_json(file_path.read_bytes())


def save_json(file_path: Path, data: Union[dict, list], indent: int = 4):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
