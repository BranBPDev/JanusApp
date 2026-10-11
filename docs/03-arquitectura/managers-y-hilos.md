[⬅ Volver al README](../../README.md)

# Managers e hilos de trabajo (`app/managers`)

## `AppManager`

Coordina el arranque. Crea la `UpdateWindow` y el `UpdateWorker` y conecta sus señales:

| Señal del worker | Acción |
|---|---|
| `update_found(local, remote)` | `UpdateWindow.show_update` |
| `progress(f, msg)` | `UpdateWindow.set_progress` |
| `restart()` | `_on_restart`: cierra la app para completar la actualización |
| `failed(msg)` | Abre la ventana principal con el aviso de fallo |
| `done()` | Abre la ventana principal |

`_open_main` es idempotente. `_on_restart` permite el cierre de la ventana de actualización, hace `quit()` a los 800 ms y, como garantía, `os._exit(0)` a los 3000 ms para que el script pueda reemplazar los archivos.

## `UpdateWorker` (`QThread`)

Señales: `update_found(str, str)`, `progress(float, str)`, `restart()`, `failed(str)`, `done()`.

```
check_for_update()
  ├─ None                → done
  ├─ no IS_FROZEN        → done (se omite en desarrollo)
  └─ UpdateInfo          → update_found → perform_update → restart
  (cualquier excepción)  → failed
```

## `ShapeWorker` (`QThread`)

Genera y guarda la forma sin bloquear la interfaz.

| Señal | Contenido |
|---|---|
| `progress(float, str)` | Fracción 0–1 y mensaje |
| `finished_ok(object, str)` | `ShapeResult` y carpeta del proyecto |
| `failed(str)` | Mensaje de error |

`run()`: `generate_shape` → progreso 0,95 «Guardando proyecto...» → `save_shape` → progreso 1,0 «Completado» → `finished_ok`. Los errores se registran con traza en el log.

Detalle del pipeline: [Pipeline completo](../04-pipeline-de-forma/pipeline.md).
