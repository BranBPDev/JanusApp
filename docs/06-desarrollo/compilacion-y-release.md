[⬅ Volver al README](../../README.md)

# Compilación y publicación de releases

## Compilar en local

```powershell
pyinstaller --clean --noconfirm JanusApp.spec
```

Genera `dist/JanusApp.exe`.

## `JanusApp.spec`

- Un único ejecutable (*onefile*), sin consola, con el icono `app/assets/logo.ico`.
- Incluye `app/assets` como datos.
- Excluye `tkinter`, `numpy.f2py` y `PIL.ImageTk`.
- Elimina componentes de Qt que no se usan (QML, Quick, PDF, SVG, teclado virtual, `opengl32sw.dll`, plugins `qdirect2d`/`qminimal`/`qoffscreen`, carpetas `translations`...) para reducir la descarga.

## `version.json`

```json
{
  "configs": {
    "tag": "v0.0.2",
    "name": "JanusApp v0.0.2",
    "description": "Texto de la release",
    "prerelease": false,
    "make_latest": true,
    "branch": "main"
  },
  "userjson": {
    "name": "JanusApp",
    "version": "0.0.2",
    "releaseDate": "2026-10-08",
    "author": "BranBP",
    "repository": "https://github.com/BranBPDev/JanusApp"
  }
}
```

- `configs`: lo usa el workflow para crear la release. **No** se distribuye.
- `userjson`: es lo que se distribuye (`app/data/version.json`) y lo que lee la aplicación para mostrar y comparar versiones.

## Workflow `build_release.yml`

**Disparador**: `push` a `main`, ignorando `testing/**` y `**.md` (cambiar la documentación **no** lanza una release). Concurrencia `release` con cancelación de ejecuciones anteriores. Corre en `windows-latest`.

| Paso | Qué hace |
|---|---|
| Checkout | `actions/checkout@v4` |
| Python | 3.11 con caché de pip |
| Dependencias | `pip install -r requirements.txt` |
| Configuración del release | Lee `version.json`, exporta `TAG`, `REL_NAME`, `DESC`, `PRE`, `LATEST` a `GITHUB_ENV` y reescribe `version.json` solo con `userjson` |
| Compilar | `pyinstaller --clean --noconfirm JanusApp.spec` |
| ZIP final | Crea `release_build/` con `JanusApp.exe` y `app/data/version.json`; lo comprime sin compresión (el `.exe` ya viene comprimido) |
| Publicar | `softprops/action-gh-release@v2` con `JanusApp.zip` y `version.json`, `overwrite: true` |

Necesita el permiso `contents: write` (ya declarado) y usa `GITHUB_TOKEN`.

## Cómo publicar una nueva versión

1. Edita `version.json`: sube `configs.tag`, `configs.name`, `userjson.version` y `userjson.releaseDate`, y actualiza la descripción.
2. Haz commit y push a `main`.
3. El workflow compila y publica. Los clientes se actualizarán al abrir la aplicación.

> Un push que solo toque archivos `.md` o `testing/` no genera release.
