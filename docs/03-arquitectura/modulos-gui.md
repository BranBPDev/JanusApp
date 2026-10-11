[⬅ Volver al README](../../README.md)

# Interfaz gráfica (`app/gui`)

## `main_window.py`

- `SECTIONS`: lista `(clave, texto)` de la barra lateral: `home` (Inicio), `shape` (Forma), `texture` (Texturas), `collision` (Colisión), `rig` (Esqueleto), `viewer` (Visor 3D). **Las futuras fases se añaden aquí.**
- `HomePage`: bienvenida y tarjetas con versión, fecha de publicación y autor (leídos de `version.json`).
- `PlaceholderPage`: página con «Próximamente» para las secciones aún sin implementar.
- `MainWindow`: ventana de 1280×800 (mínimo 1000×650) con barra lateral de 220 px, `QStackedWidget` y barra de estado. `notify(mensaje, msec)` muestra un aviso temporal.
- `make_card(titulo, valor)`: tarjeta reutilizable.

## `shape_page.py`

Pantalla de generación. Piezas principales:

| Elemento | Función |
|---|---|
| `VIEWS` | Las 6 vistas: clave, título y palabras reconocibles en el nombre |
| `classify(nombre)` | Devuelve `(vista o None, es_malla)` |
| `object_name(rutas)` | Deduce el nombre del objeto |
| `Preview` | Casilla con botón +, papelera y arrastrar/soltar |
| `ViewPair` | Una vista y su malla |
| `ShapePage` | Panel izquierdo (carga y generación) y derecho (visor, LODs, información) |

Flujo: `_load_files` → `_generate` (valida) → `ShapeWorker` → `_on_progress` / `_on_failed` / `_on_done` → `_show_lod`.

Con objetos paramétricos los botones LOD quedan desactivados (`not result.descriptor`).

## `theme.py`

- `COLORS`: paleta oscura (`bg`, `surface`, `elevated`, `border`, `hover`, `text`, `muted`, `disabled`, `accent`, `accent_hover`, `accent_soft`, `success`, `warning`).
- `_QSS`: hoja de estilos con `string.Template`; los widgets se estilan por `objectName` (`Title`, `Subtitle`, `Muted`, `Card`, `NavButton`, `Primary`, `Seg`, `Thumb`, `Warn`...).
- `apply_theme(app)`: estilo Fusion, fuente Segoe UI 10, paleta y QSS.

## `update_window.py`

Ventana sin marco, siempre visible y arrastrable. Muestra logo, estado y barra (indeterminada al principio, determinada al descargar). No se puede cerrar hasta llamar a `allow_close()` / `finish()`.

## `viewer.py`

`MeshViewer`: ver [Visor 3D por software](../04-pipeline-de-forma/visor.md).

Siguiente: [Managers e hilos](managers-y-hilos.md)
