[⬅ Volver al README](../../README.md)

# Utilidades (`app/utils`)

| Módulo | Contenido |
|---|---|
| `paths_util.py` | Todas las rutas y URLs de la aplicación |
| `logger_util.py` | Logging rotativo y `excepthook` |
| `json_util.py` | `parse_json`, `read_json`, `save_json` |
| `download_util.py` | `http_get`, `download_file` |
| `zip_util.py` | `unzip_file` |
| `callback_util.py` | `invoke_progress` |
| `update_util.py` | Lógica de actualización (ver [Actualizaciones](../05-actualizaciones/sistema-de-actualizacion.md)) |

## `paths_util.py`

- `APP_NAME = "JanusApp"`, `GITHUB_REPO = "BranBPDev/JanusApp"`.
- `IS_FROZEN`: `True` dentro del `.exe` de PyInstaller.
- `BASE_DIR`: carpeta del `.exe` (o raíz del repo en desarrollo).
- `APP_DIR = BASE_DIR/app`, con `DATA_DIR`, `LOGS_DIR`, `PROJECTS_DIR`, `SETTINGS_DIR`.
- `USER_DATA_DIRS = (LOGS_DIR, PROJECTS_DIR, SETTINGS_DIR)`: lo que una actualización nunca borra.
- `ASSETS_DIR`, `LOGO_PNG`, `LOGO_ICO`, `UPDATE_SCRIPT`: recursos dentro del bundle.
- `VERSION_JSON`: `app/data/version.json` en el `.exe`; `version.json` de la raíz en desarrollo.
- `DOWNLOAD_FOLDER` (`temp_download`), `TEMP_ZIP_PATH`, `STAGING_DIR`.
- `REMOTE_VERSION_JSON` y `LATEST_ZIP_URL`: apuntan a `releases/latest/download`.

## `logger_util.py`

- Logger raíz `janus`, nivel DEBUG, formato `fecha [NIVEL] [nombre] mensaje`.
- `RotatingFileHandler` en `app/logs/janus.log` (5 MB, 3 copias).
- Salida a consola solo si no es el `.exe`.
- `install_excepthook()` registra excepciones no capturadas como críticas.
- `shutdown_logs()` cierra los handlers (se llama antes de lanzar el actualizador).

## `download_util.py`

- `http_get(url, timeout=6)`: GET simple con redirecciones y cabecera `JanusApp-Updater`.
- `download_file(url, path, callback, timeout=30)`: descarga en bloques de 512 KB a `<archivo>.part`, comprueba el tamaño y lo renombra al terminar. Nunca deja archivos a medias.

## `json_util.py`

`parse_json` tolera BOM UTF-8. `read_json` lanza `FileNotFoundError` si no existe. `save_json` crea carpetas y escribe con indentación 4 y `ensure_ascii=False`.

## `zip_util.py`

`unzip_file(zip, destino, progress)` extrae miembro a miembro e informa del progreso cada 25 archivos.

## `callback_util.py`

`invoke_progress(callback, fraccion, mensaje)` limita la fracción a 0–1 y traga cualquier excepción del callback para que no rompa el proceso.
