[⬅ Volver al README](../../README.md)

# Visión general de la arquitectura

JanusApp es una aplicación **PySide6 (Qt 6)** con numpy y Pillow. Se empaqueta con PyInstaller en un único `.exe`.

## Capas

```
main.py
  └── AppManager ──────────────► ventanas (app/gui)
        ├── UpdateWorker (QThread) ──► app/utils/update_util
        └── MainWindow
              └── ShapePage
                    └── ShapeWorker (QThread) ──► app/shape/pipeline ──► app/shape/project
```

| Capa | Carpeta | Responsabilidad |
|---|---|---|
| Entrada | `main.py` | Logging, `excepthook`, AppUserModelID, tema, arranque del `AppManager` |
| Interfaz | `app/gui` | Widgets y estilos. Sin lógica de negocio |
| Managers | `app/managers` | Orquestan y lanzan hilos (`QThread`) comunicándose por señales |
| Dominio | `app/shape` | Generación de la forma 3D (numpy puro, sin Qt salvo el visor) |
| Utilidades | `app/utils` | Rutas, logs, JSON, descargas, zip, actualización |
| Recursos | `app/assets` | Logo y script de actualización de PowerShell |

## Flujo de arranque

1. `main.py` registra el inicio, instala el `excepthook` y fija el AppUserModelID (`BranBP.JanusApp`) en Windows.
2. Crea la `QApplication`, el icono y aplica el tema oscuro.
3. `AppManager` muestra la `UpdateWindow` y lanza el `UpdateWorker`.
4. Según el resultado:
   - Sin actualización (o en desarrollo) → abre la `MainWindow`.
   - Actualización aplicada → cierra la app para que `update.ps1` reemplace los archivos y la relance.
   - Fallo → abre la `MainWindow` con el aviso *"No se pudo actualizar la aplicación."*.
5. Al salir se hace `os._exit(code)` para cerrar aunque haya un hilo activo.

## Principios de diseño

- **Todo lo pesado en hilos**: la interfaz solo escucha señales (`progress`, `finished_ok`, `failed`).
- **Dominio sin Qt**: `Scene` (render) y todo `app/shape` calculan con numpy; solo `viewer.py` pinta.
- **Datos de usuario fuera del bundle**: se guardan junto al `.exe` y sobreviven a las actualizaciones.
- **Una única textura** por objeto, compartida por todos los LODs.

Ver también: [Estructura del proyecto](estructura-del-proyecto.md), [Pipeline completo](../04-pipeline-de-forma/pipeline.md).
