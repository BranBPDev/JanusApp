import os
import time
import urllib.request
from pathlib import Path
from app.utils.callback_util import invoke_progress

HEADERS = {"User-Agent": "JanusApp-Updater", "Accept": "*/*", "Accept-Encoding": "identity"}
CHUNK = 512 * 1024


def http_get(url: str, timeout: float = 6.0) -> bytes:
    """GET sencillo (sigue las redirecciones de GitHub Releases)."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def download_file(url: str, path: Path, progress_callback=None, timeout: float = 30.0):
    """Descarga en streaming a '<path>.part' y lo renombra al terminar (nunca deja archivos a medias)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    req = urllib.request.Request(url, headers=HEADERS)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(part, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done, last = 0, 0.0
            while True:
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                now = time.monotonic()
                if now - last >= 0.05:
                    last = now
                    mb = done / 1048576
                    if total:
                        invoke_progress(progress_callback, done / total, f"Descargando... {mb:.1f} / {total / 1048576:.1f} MB")
                    else:
                        invoke_progress(progress_callback, 0.0, f"Descargando... {mb:.1f} MB")
        if total and done != total:
            raise IOError(f"Descarga incompleta ({done}/{total} bytes)")
        os.replace(part, path)
    finally:
        if part.exists():
            part.unlink(missing_ok=True)
    invoke_progress(progress_callback, 1.0, "Descarga completada")
