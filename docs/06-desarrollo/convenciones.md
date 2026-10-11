[⬅ Volver al README](../../README.md)

# Convenciones de código

Convenciones observadas en el proyecto; conviene mantenerlas al añadir código.

## Organización

- **`gui`**: solo widgets, estilos y reacción a señales. Sin cálculo pesado.
- **`managers`**: clases `QThread` (`*Worker`) que orquestan y emiten señales; `AppManager` coordina ventanas.
- **`shape`**: lógica de dominio con numpy, sin dependencia de Qt (salvo lo que pinte el visor).
- **`utils`**: funciones sueltas, un tema por archivo con sufijo `_util.py`.

## Hilos y progreso

- Todo trabajo largo va en un `QThread` con señales `progress(float, str)`, `finished_ok(...)`/`done` y `failed(str)`.
- El progreso se notifica con fracciones 0–1 y, en utilidades, mediante `invoke_progress`, que nunca propaga excepciones.

## Interfaz

- Los widgets se estilan **por `objectName`** desde `theme.py`; no se aplican estilos en línea.
- Los colores salen de `COLORS`; no se escriben colores sueltos (salvo los iconos verde/rojo de `Preview`).
- Textos de interfaz y mensajes de log en **español**.

## Datos de usuario

- Todo lo que el usuario genera va bajo `app/` y debe estar en `USER_DATA_DIRS` si no debe borrarse al actualizar.
- Las rutas se definen **solo** en `paths_util.py`.

## Registro y errores

- `get_logger("NOMBRE")` por módulo; los errores se registran con `exc_info=True`.
- Las excepciones de validación del dominio usan `ValueError` con mensaje legible, que se muestra tal cual al usuario.

## Estilo

- Docstrings breves en español explicando el *qué* y las unidades/convenciones de ejes.
- Constantes en mayúsculas al principio del módulo, con comentario si no son evidentes.
- Tipado ligero (`Optional`, `dataclass`) donde aporta claridad.

## Añadir una nueva fase

1. Añadir `(clave, texto)` a `SECTIONS` en `main_window.py` y crear su página.
2. Crear su worker en `app/managers/`.
3. Si guarda datos, añadir la clave a `PHASES` en `project.py` y escribirla en el manifest.
4. Documentarla en `docs/` y enlazarla desde el `README.md`.
