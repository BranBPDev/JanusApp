import numpy as np

# Convención de colores de las mallas (capa de marcas):
#   rojo  -> línea de corte: por aquí se abre el objeto (tapa, boca, puerta...)
#   verde -> punto dentro de la parte que se mueve (opcional; por defecto la parte de arriba del corte)
#   azul  -> punto en la bisagra (opcional; por defecto el borde trasero del corte)


def role(color_hex: str):
    r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)
    if r > 150 and g < 110 and b < 110:
        return "corte"
    if g > 130 and r < 120 and b < 120:
        return "mueve"
    if b > 150 and r < 100 and g < 130:
        return "bisagra"
    return None


def _marks(marks, key, name):
    return [m for m in marks.get(key, []) if role(m["color"]) == name]


def _to_world(key, x, y, dims):
    """Coordenadas de una marca (metros desde la esquina inferior izquierda del objeto en esa vista) -> mundo (x, y, z)."""
    w, h, d = dims
    if key == "front":
        return np.array([x - w / 2, y, 0.0])
    if key == "back":
        return np.array([w / 2 - x, y, 0.0])
    if key == "right":
        return np.array([0.0, y, x - d / 2])
    if key == "left":
        return np.array([0.0, y, d / 2 - x])
    if key == "top":
        return np.array([x - w / 2, 0.0, d / 2 - y])
    return np.array([x - w / 2, 0.0, y - d / 2])


def find_opening(marks: dict, dims_m, height_m):
    """A partir de las marcas de las mallas devuelve {'point', 'normal', 'hinge'} en unidades del modelo (alto = 1)
    y una lista de avisos. 'normal' apunta hacia la parte que se mueve."""
    warnings, plane = [], None
    dims = tuple(dims_m)

    for key in ("right", "left"):                       # línea de corte vista de lado: cualquier inclinación
        segs = [seg for m in _marks(marks, key, "corte") for seg in m["segments_m"]]
        if segs:
            a, b = max(segs, key=lambda sg: np.hypot(sg[1][0] - sg[0][0], sg[1][1] - sg[0][1]))
            p1, p2 = _to_world(key, *a, dims), _to_world(key, *b, dims)
            dz, dy = p2[2] - p1[2], p2[1] - p1[1]
            n = np.array([0.0, -dz, dy])
            if n[1] < -1e-9 or (abs(n[1]) <= 1e-9 and n[2] < 0):
                n = -n
            plane = ((p1 + p2) / 2, n / np.linalg.norm(n), key)
            break
    if plane is None:
        for key in ("front", "back"):                   # línea horizontal vista de frente: plano horizontal
            segs = [seg for m in _marks(marks, key, "corte") for seg in m["segments_m"]]
            if segs:
                a, b = max(segs, key=lambda sg: abs(sg[1][0] - sg[0][0]))
                if abs(b[1] - a[1]) > 0.1 * max(abs(b[0] - a[0]), 1e-9):
                    warnings.append("La línea de corte de la vista frontal está inclinada: dibújala también en una vista lateral.")
                    continue
                y = (a[1] + b[1]) / 2
                plane = (np.array([0.0, y, 0.0]), np.array([0.0, 1.0, 0.0]), key)
                break
    if plane is None:
        if any(_marks(marks, k, "corte") for k in marks):
            warnings.append("Hay una marca de corte que no se puede interpretar (se necesita una línea en una vista lateral o una línea horizontal de frente).")
        return None, warnings

    point, normal, _ = plane

    # parte que se mueve: punto verde (la normal pasa a apuntar hacia él)
    for key in ("right", "left", "front", "back"):
        dots = [pt for m in _marks(marks, key, "mueve") for pt in m["points_m"]]
        if dots:
            side = (_to_world(key, *dots[0], dims) - point) @ normal
            if side < 0:
                normal = -normal
            break

    hinge = None
    for key in ("right", "left"):
        dots = [pt for m in _marks(marks, key, "bisagra") for pt in m["points_m"]]
        if dots:
            hinge = _to_world(key, *dots[0], dims)
            break

    return {"point": point / height_m, "normal": normal, "hinge": None if hinge is None else hinge / height_m}, warnings
