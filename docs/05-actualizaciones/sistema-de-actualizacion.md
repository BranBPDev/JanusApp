[⬅ Volver al README](../../README.md)

# Sistema de actualización automática

Componentes: `app/utils/update_util.py`, `app/managers/update_manager.py`, `app/gui/update_window.py` y `app/assets/scripts/update.ps1`.

## Resumen del flujo

```
Arranque → UpdateWindow + UpdateWorker
  1. Lee version.json local
  2. Descarga version.json remoto (releases/latest/download)
  3. ¿remota > local?  no → abre la app
  4. ¿IS_FROZEN?       no → abre la app (desarrollo)
  5. Descarga JanusApp.zip  → temp_download/update.zip   (0–90 %)
  6. Descomprime            → temp_download/payload       (90–100 %)
  7. Comprueba que existe JanusApp.exe en el paquete
  8. Copia update.ps1 a %TEMP% y lo lanza desvinculado
  9. La app se cierra  →  el script reemplaza archivos y relanza el .exe
```

## Versiones

- `parse_version("v1.2.3")` → `(1, 2, 3, 0)`: se extraen hasta 4 números, así `1.10 > 1.9`.
- `version.json` puede ser el completo (`configs` + `userjson`) o el limpio de la release; `_user_info` acepta ambos.
- Sin red, o si falla la lectura remota, se continúa sin actualizar.

## Descarga (`download_util`)

Se descarga a `update.zip.part` y solo se renombra al terminar y comprobar el tamaño (`Content-Length`). Si algo falla se elimina la carpeta `temp_download`.

## Script `update.ps1`

Parámetros: `-ProcId`, `-BaseDir`, `-StagingDir`, `-DownloadDir`, `-ExePath`, `-LogPath`, `-Keep`.

1. Espera hasta 60 s a que termine el proceso de la aplicación.
2. Crea `_backup/` (borrando una anterior).
3. `Clear-Targets`: mueve a `_backup/` todo lo que va a ser reemplazado. Dentro de `app/` **conserva** los directorios de `-Keep` (`logs`, `projects`, `settings`).
4. Copia el contenido de `payload` sobre `BaseDir`.
5. Borra `_backup/` y `temp_download/`.
6. Relanza `JanusApp.exe`.

**Si algo falla**: restaura la copia de seguridad, borra `temp_download/` y relanza igualmente la aplicación.

Todas las operaciones sobre archivos se reintentan hasta 20 veces cada 500 ms (antivirus o *handles* abiertos pueden bloquearlos unos instantes). El script escribe en `app/logs/janus.log` con la etiqueta `[PS_UPDATER]`.

## Cierre de la aplicación

`AppManager._on_restart` permite cerrar la ventana de actualización, llama a `quit()` a los 800 ms y a `os._exit(0)` a los 3000 ms. Antes de lanzar el script se cierran los logs (`shutdown_logs`) y se limpian del entorno las variables `_MEIPASS*` / `_PYI*` para que el nuevo proceso no herede el bundle anterior.

## Qué se publica

El workflow sube `JanusApp.zip` y `version.json` a la release. Ver [Compilación y publicación](../06-desarrollo/compilacion-y-release.md).

> Para que los usuarios reciban una actualización hay que **subir la versión** en `version.json` (`configs.tag` y `userjson.version`).
