[⬅ Volver al README](../../README.md)

# Estructura del proyecto

```
JanusApp/
├── .github/workflows/build_release.yml   CI: compila y publica la release
├── app/
│   ├── assets/
│   │   ├── logo.ico / logo.png
│   │   └── scripts/update.ps1            Reemplazo de archivos en la actualización
│   ├── gui/
│   │   ├── main_window.py                Ventana principal, barra lateral, Inicio
│   │   ├── shape_page.py                 Pantalla «Forma»
│   │   ├── theme.py                      Paleta y hoja de estilos (QSS)
│   │   ├── update_window.py              Ventana de arranque / actualización
│   │   └── viewer.py                     Visor 3D por software
│   ├── managers/
│   │   ├── app_manager.py                Coordina ventanas y arranque
│   │   ├── shape_manager.py              ShapeWorker (hilo de generación)
│   │   └── update_manager.py             UpdateWorker (hilo de actualización)
│   ├── shape/                            Pipeline de generación 3D
│   │   ├── atlas.py       cut.py         ellipsoid.py     export.py
│   │   ├── field.py       mesh_ops.py    metric.py        model.py
│   │   ├── opening.py     pipeline.py    preprocess.py    primitive.py
│   │   └── project.py     qem.py         render.py        surface_nets.py
│   └── utils/
│       ├── callback_util.py  download_util.py  json_util.py   logger_util.py
│       └── paths_util.py     update_util.py    zip_util.py
├── docs/                                 Esta documentación
├── .gitignore
├── JanusApp.spec                         Configuración de PyInstaller
├── main.py                               Punto de entrada
├── requirements.txt
└── version.json                          Versión y configuración de la release
```

## Directorios que genera la ejecución (ignorados por git)

`app/logs/`, `app/projects/`, `app/settings/`, `temp_download/`, `_backup/`, `build/`, `dist/`, `testing/`.

## Dónde mirar según la tarea

| Quiero... | Archivo |
|---|---|
| Añadir una sección a la barra lateral | `app/gui/main_window.py` (`SECTIONS`) |
| Cambiar colores o estilos | `app/gui/theme.py` |
| Cambiar cómo se genera la forma | `app/shape/pipeline.py` |
| Cambiar qué se guarda en disco | `app/shape/project.py`, `app/shape/export.py` |
| Cambiar rutas o la URL de releases | `app/utils/paths_util.py` |
| Cambiar la lógica de actualización | `app/utils/update_util.py`, `app/assets/scripts/update.ps1` |

Siguiente: [Interfaz gráfica](modulos-gui.md)
