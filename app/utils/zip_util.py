import zipfile
from pathlib import Path


def unzip_file(zip_path: Path, extract_to: Path, progress=None):
    """Descomprime (zipfile ya neutraliza rutas '..'). progress(fraction) opcional. Lanza excepción si falla."""
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.infolist()
        total = len(members) or 1
        for i, member in enumerate(members, 1):
            zf.extract(member, extract_to)
            if progress and (i % 25 == 0 or i == total):
                progress(i / total)
