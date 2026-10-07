import sys
from pathlib import Path

APP_NAME = "JanusApp"
GITHUB_REPO = "BranBPDev/JanusApp"

IS_FROZEN = getattr(sys, "frozen", False)

if IS_FROZEN:
    EXE_PATH = Path(sys.executable).resolve()
    BASE_DIR = EXE_PATH.parent
    INTERNAL_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parents[2]
    INTERNAL_DIR = BASE_DIR
    EXE_PATH = BASE_DIR / f"{APP_NAME}.exe"

# --- Carpetas (fuera del bundle: persisten y se pueden escribir) ---
APP_DIR = BASE_DIR / "app"
DATA_DIR = APP_DIR / "data"
LOGS_DIR = APP_DIR / "logs"
PROJECTS_DIR = APP_DIR / "projects"
SETTINGS_DIR = APP_DIR / "settings"

# Datos del usuario que una actualización NUNCA debe borrar (dentro de 'app').
USER_DATA_DIRS = (LOGS_DIR, PROJECTS_DIR, SETTINGS_DIR)

LOGS_DIR.mkdir(parents=True, exist_ok=True)
MAIN_LOG_PATH = LOGS_DIR / "janus.log"

# --- Recursos incluidos en el bundle ---
ASSETS_DIR = INTERNAL_DIR / "app" / "assets"
LOGO_PNG = ASSETS_DIR / "logo.png"
LOGO_ICO = ASSETS_DIR / "logo.ico"
UPDATE_SCRIPT = ASSETS_DIR / "scripts" / "update.ps1"

# En el .exe la versión viaja en app/data; en desarrollo se lee del version.json de la raíz.
VERSION_JSON = DATA_DIR / "version.json" if IS_FROZEN else BASE_DIR / "version.json"

# --- Actualización ---
DOWNLOAD_FOLDER = BASE_DIR / "temp_download"
TEMP_ZIP_PATH = DOWNLOAD_FOLDER / "update.zip"
STAGING_DIR = DOWNLOAD_FOLDER / "payload"

RELEASE_BASE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest/download"
REMOTE_VERSION_JSON = f"{RELEASE_BASE_URL}/version.json"
LATEST_ZIP_URL = f"{RELEASE_BASE_URL}/{APP_NAME}.zip"
