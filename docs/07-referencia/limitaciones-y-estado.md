[⬅ Volver al README](../../README.md)

# Limitaciones y estado actual

Versión documentada: **v0.0.2** (2026-10-08).

## Estado de las secciones

| Sección | Estado |
|---|---|
| Inicio | Implementada |
| Forma | Implementada |
| Texturas | «Próximamente» (la textura básica ya se genera dentro de Forma) |
| Colisión | «Próximamente» |
| Esqueleto | «Próximamente» |
| Visor 3D | «Próximamente» (el visor existe dentro de Forma) |

El manifest ya reserva las fases `collision` y `rig`.

## Limitaciones conocidas

- **Plataforma**: solo Windows (actualización por PowerShell, AppUserModelID).
- **Escala**: imprescindible una malla por cada vista cargada; sin cuadrícula regular la generación se detiene.
- **Mínimo de vistas**: frente + una lateral.
- **Resolución de textura**: limitada a 256 px (`cap` del atlas); 256×128 en objetos paramétricos.
- **Apertura**:
  - Eje de giro fijo en X y ángulo de 75°.
  - El corte debe formar un único contorno cerrado.
  - Solo dos piezas (fija y móvil), huecas con una cúpula interior simple.
  - El corte desde la vista frontal solo admite líneas horizontales.
- **Forma del volumen**: casco visual; no reconstruye concavidades que no se vean en las siluetas.
- **Rendimiento**: la decimación (`qem.py`) está en Python puro y es la parte más lenta con mallas grandes.
- **Visor**: por software (sin OpenGL), con orden de profundidad por triángulo; puede mostrar artefactos en geometrías complejas.
- **Objetos paramétricos**: el motor que los use debe aportar su propia esfera/elipsoide y UV equirrectangular.
- **Actualización**: solo en el `.exe`; se omite en desarrollo.

## Si algo falla

1. Lee el mensaje en la línea de estado o los avisos amarillos del panel derecho.
2. Revisa `app/logs/janus.log`.
3. Comprueba en [Preparar las vistas](../02-guia-de-usuario/preparar-vistas.md) y [Mallas y marcas](../02-guia-de-usuario/mallas-y-marcas.md) que las imágenes cumplen los requisitos.
