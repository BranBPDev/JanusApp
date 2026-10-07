import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional

from app.utils.callback_util import invoke_progress
from app.utils.download_util import download_file, http_get
from app.utils.json_util import parse_json, read_json
from app.utils.logger_util import get_logger, shutdown_logs
from app.utils.paths_util import (
    APP_NAME, BASE_DIR, DOWNLOAD_FOLDER, EXE_PATH, IS_FROZEN, LATEST_ZIP_URL, MAIN_LOG_PATH,
    REMOTE_VERSION_JSON, STAGING_DIR, TEMP_ZIP_PATH, UPDATE_SCRIPT, USER_DATA_DIRS, VERSION_JSON,
)
from app.utils.zip_util import unzip_file

log = get_logger("UPDATER")

CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


@dataclass(frozen=True)
class UpdateInfo:
    local: str
    remote: str


def parse_version(version: str) -> tuple:
    """'v1.2.3' -> (1, 2, 3, 0). Permite comparar versiones correctamente (1.10 > 1.9)."""
    nums = [int(n) for n in re.findall(r"\d+", version or "")][:4]
    return tuple(nums + [0] * (4 - len(nums)))


def _user_info(data: dict) -> dict:
    """Acepta tanto el version.json completo (configs + userjson) como el limpio del release."""
    return data.get("userjson", data)


def get_local_info() -> dict:
    try:
        return _user_info(read_json(VERSION_JSON))
    except Exception as e:
        log.error(f"No se pudo leer el version.json local: {e}")
        return {}


def get_local_version() -> str:
    return str(get_local_info().get("version", "0.0.0"))


def fetch_remote_version() -> Optional[str]:
    try:
        return str(_user_info(parse_json(http_get(REMOTE_VERSION_JSON)))["version"])
    except Exception as e:
        log.warning(f"No se pudo obtener la versión remota: {e}")
        return None


def check_for_update() -> Optional[UpdateInfo]:
    """Devuelve UpdateInfo si hay una versión remota MÁS NUEVA; None si está al día o no hay red."""
    log.info("Verificando si existe una nueva versión disponible...")
    local = get_local_version()
    remote = fetch_remote_version()
    if remote is None:
        return None
    log.info(f"Versión local: {local} | Versión remota: {remote}")
    if parse_version(remote) > parse_version(local):
        log.info("Nueva versión detectada.")
        return UpdateInfo(local, remote)
    log.info("La aplicación ya está en la última versión.")
    return None


def _launch_updater():
    """Copia el script a %TEMP% y lo lanza desvinculado: espera al cierre, reemplaza archivos y relanza."""
    script = os.path.join(tempfile.gettempdir(), "janus_update.ps1")
    shutil.copyfile(UPDATE_SCRIPT, script)

    cmd = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", script,
        "-ProcId", str(os.getpid()),
        "-BaseDir", str(BASE_DIR),
        "-StagingDir", str(STAGING_DIR),
        "-DownloadDir", str(DOWNLOAD_FOLDER),
        "-ExePath", str(EXE_PATH),
        "-LogPath", str(MAIN_LOG_PATH),
        "-Keep", ",".join(d.name for d in USER_DATA_DIRS),
    ]
    # Sin variables de PyInstaller para que la app relanzada arranque limpia.
    env = {k: v for k, v in os.environ.items() if not k.startswith(("_MEIPASS", "_PYI"))}
    log.info(f"PID actual: {os.getpid()} | Lanzando script de actualización: {script}")
    shutdown_logs()
    subprocess.Popen(
        cmd, env=env, close_fds=True, creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def perform_update(progress_callback=None):
    """Descarga + descomprime + lanza el reemplazo. Tras volver, la app debe cerrarse. Lanza excepción si falla."""
    if not IS_FROZEN:
        raise RuntimeError("La actualización solo está disponible en el ejecutable compilado.")

    log.info("Iniciando proceso de actualización...")
    try:
        shutil.rmtree(DOWNLOAD_FOLDER, ignore_errors=True)
        DOWNLOAD_FOLDER.mkdir(parents=True)

        log.info(f"Descargando {LATEST_ZIP_URL}")
        download_file(LATEST_ZIP_URL, TEMP_ZIP_PATH,
                      lambda f, m: invoke_progress(progress_callback, f * 0.9, m))

        invoke_progress(progress_callback, 0.9, "Descomprimiendo archivos...")
        unzip_file(TEMP_ZIP_PATH, STAGING_DIR,
                   lambda f: invoke_progress(progress_callback, 0.9 + f * 0.1, "Descomprimiendo archivos..."))
        TEMP_ZIP_PATH.unlink(missing_ok=True)

        if not (STAGING_DIR / f"{APP_NAME}.exe").exists():
            raise RuntimeError(f"El paquete descargado no contiene {APP_NAME}.exe")

        invoke_progress(progress_callback, 1.0, "Reiniciando...")
        _launch_updater()
    except Exception:
        shutil.rmtree(DOWNLOAD_FOLDER, ignore_errors=True)
        raise
