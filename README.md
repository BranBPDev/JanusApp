# JanusApp

Aplicación de escritorio (Windows) que convierte vistas 2D de un objeto en modelos 3D optimizados.
Este archivo es únicamente un índice: toda la documentación está en la carpeta [`docs/`](docs/).

## 1. Primeros pasos
- [Instalación](docs/01-primeros-pasos/instalacion.md)
- [Uso rápido](docs/01-primeros-pasos/uso-rapido.md)

## 2. Guía de usuario
- [Preparar las vistas](docs/02-guia-de-usuario/preparar-vistas.md)
- [Mallas y marcas de apertura](docs/02-guia-de-usuario/mallas-y-marcas.md)
- [Generar el modelo 3D](docs/02-guia-de-usuario/generar-modelo.md)
- [Archivos generados (proyectos)](docs/02-guia-de-usuario/archivos-generados.md)

## 3. Arquitectura
- [Visión general](docs/03-arquitectura/vision-general.md)
- [Estructura del proyecto](docs/03-arquitectura/estructura-del-proyecto.md)
- [Interfaz gráfica (`app/gui`)](docs/03-arquitectura/modulos-gui.md)
- [Managers e hilos de trabajo (`app/managers`)](docs/03-arquitectura/managers-y-hilos.md)
- [Utilidades (`app/utils`)](docs/03-arquitectura/utilidades.md)

## 4. Pipeline de forma (`app/shape`)
- [Pipeline completo](docs/04-pipeline-de-forma/pipeline.md)
- [Preprocesado de siluetas](docs/04-pipeline-de-forma/preprocesado.md)
- [Escala métrica y análisis de mallas](docs/04-pipeline-de-forma/escala-metrica.md)
- [Orientación de vistas y volumen](docs/04-pipeline-de-forma/orientacion-y-volumen.md)
- [Primitivas y elipsoides](docs/04-pipeline-de-forma/primitivas.md)
- [Apertura del objeto](docs/04-pipeline-de-forma/apertura.md)
- [Atlas de texturas](docs/04-pipeline-de-forma/atlas-y-texturas.md)
- [Decimación y LODs](docs/04-pipeline-de-forma/decimacion-lods.md)
- [Exportación (GLB / OBJ)](docs/04-pipeline-de-forma/exportacion.md)
- [Visor 3D por software](docs/04-pipeline-de-forma/visor.md)

## 5. Actualizaciones
- [Sistema de actualización automática](docs/05-actualizaciones/sistema-de-actualizacion.md)

## 6. Desarrollo
- [Entorno de desarrollo](docs/06-desarrollo/entorno-de-desarrollo.md)
- [Compilación y publicación de releases](docs/06-desarrollo/compilacion-y-release.md)
- [Convenciones de código](docs/06-desarrollo/convenciones.md)

## 7. Referencia
- [Constantes y parámetros](docs/07-referencia/constantes.md)
- [Formato de `manifest.json`](docs/07-referencia/manifest-json.md)
- [Glosario](docs/07-referencia/glosario.md)
- [Limitaciones y estado actual](docs/07-referencia/limitaciones-y-estado.md)
