import numpy as np

from app.shape.geometry.coords import view_to_world
from app.shape.spec.marks import Marks

# Marcas que definen la apertura (ver spec.schema): corte (línea), mueve (punto), bisagra (punto), boton (círculo de frente).


def find_opening(marks: Marks, dims_m, height_m):
    """A partir de las marcas devuelve {'point', 'normal', 'hinge', 'button'} en unidades del modelo (alto = 1) o None, y una
    lista de avisos. 'normal' apunta hacia la parte que se mueve."""
    warnings, plane = [], None
    dims = tuple(dims_m)
    world = lambda key, p: view_to_world(key, *p, dims)

    for key in ("right", "left"):                       # línea de corte vista de lado: cualquier inclinación
        segs = marks.cut.get(key)
        if segs:
            a, b = max(segs, key=lambda sg: np.hypot(sg[1][0] - sg[0][0], sg[1][1] - sg[0][1]))
            p1, p2 = world(key, a), world(key, b)
            dz, dy = p2[2] - p1[2], p2[1] - p1[1]
            n = np.array([0.0, -dz, dy])
            if n[1] < -1e-9 or (abs(n[1]) <= 1e-9 and n[2] < 0):
                n = -n
            plane = ((p1 + p2) / 2, n / np.linalg.norm(n))
            break
    if plane is None:
        for key in ("front", "back"):                   # línea horizontal vista de frente: plano horizontal
            segs = marks.cut.get(key)
            if segs:
                a, b = max(segs, key=lambda sg: abs(sg[1][0] - sg[0][0]))
                if abs(b[1] - a[1]) > 0.1 * max(abs(b[0] - a[0]), 1e-9):
                    warnings.append("La línea de corte de la vista frontal está inclinada: dibújala también en una vista lateral.")
                    continue
                plane = (np.array([0.0, (a[1] + b[1]) / 2, 0.0]), np.array([0.0, 1.0, 0.0]))
                break
    if plane is None:
        if marks.cut:
            warnings.append("Hay una marca de corte que no se puede interpretar (se necesita una línea en una vista lateral o una línea horizontal de frente).")
        return None, warnings

    point, normal = plane
    for key in ("right", "left", "front", "back"):      # parte que se mueve: la normal pasa a apuntar hacia ella
        if marks.move.get(key):
            if (world(key, marks.move[key][0]) - point) @ normal < 0:
                normal = -normal
            break

    hinge = next((world(key, marks.hinge[key][0]) for key in ("right", "left") if marks.hinge.get(key)), None)

    button = None                                       # círculo de la vista frontal: centro (x, y) y radio
    if marks.button.get("front"):
        (cx, cy), r = marks.button["front"][0]
        button = {"center": [(cx - dims[0] / 2) / height_m, cy / height_m], "radius": r / height_m}

    return {"point": point / height_m, "normal": normal, "hinge": None if hinge is None else hinge / height_m,
            "button": button}, warnings
