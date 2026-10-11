[⬅ Volver al README](../../README.md)

# Entorno de desarrollo

## Requisitos

- Windows y Python **3.11** (la versión que usa el workflow).
- Git.

## Puesta en marcha

```powershell
git clone https://github.com/BranBPDev/JanusApp.git
cd JanusApp
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## Dependencias (`requirements.txt`)

| Paquete | Versión |
|---|---|
| PySide6 | `>=6.7,<7` |
| pyinstaller | `>=6.6` |
| pillow | `>=10` |
| numpy | `>=1.26,<3` |

## Comportamiento en desarrollo

- `IS_FROZEN = False`: `BASE_DIR` es la raíz del repositorio y la versión se lee de `version.json` de la raíz.
- La **actualización automática se omite** (se registra *"Actualización X disponible; omitida en modo desarrollo."*).
- Los logs también salen por consola.
- Los datos (`app/logs`, `app/projects`, `app/settings`) se crean en el repositorio y están en `.gitignore`.

## Datos de prueba

La carpeta `testing/` está ignorada por git y por el workflow: úsala para imágenes de prueba.

## Depuración

- Revisa `app/logs/janus.log`.
- Las excepciones no capturadas se registran como `CRASH`.
- Los errores del hilo de generación se registran con traza completa en `SHAPE_MANAGER`.

Siguiente: [Compilación y publicación](compilacion-y-release.md)
