[⬅ Volver al README](../../README.md)

# Instalación

JanusApp se distribuye como un único ejecutable de Windows (`JanusApp.exe`) publicado en las *releases* de GitHub: [BranBPDev/JanusApp](https://github.com/BranBPDev/JanusApp/releases/latest).

## Requisitos

- Windows (la actualización automática usa PowerShell y el ejecutable se compila en `windows-latest`).
- No hace falta instalar Python: el `.exe` lo incluye todo.

## Pasos

1. Descarga `JanusApp.zip` desde la última release.
2. Descomprímelo en la carpeta que quieras.
3. Ejecuta `JanusApp.exe`.

El zip contiene:

```
JanusApp.exe
app/
  data/
    version.json
```

## Carpetas que crea la aplicación

Junto al `.exe` se crea la carpeta `app/` con los datos del usuario:

| Carpeta | Contenido |
|---|---|
| `app/logs/` | `janus.log` (rotativo, 5 MB × 3 copias) |
| `app/projects/` | Proyectos generados (un directorio por objeto) |
| `app/settings/` | Ajustes del usuario |
| `app/data/` | `version.json` de la versión instalada |

> `logs`, `projects` y `settings` **nunca se borran** al actualizar. Ver [Sistema de actualización](../05-actualizaciones/sistema-de-actualizacion.md).

## Actualizaciones

Al arrancar, la aplicación comprueba si hay una versión más nueva y, si es así, se actualiza sola. No necesitas volver a descargar nada.

Siguiente: [Uso rápido](uso-rapido.md)
