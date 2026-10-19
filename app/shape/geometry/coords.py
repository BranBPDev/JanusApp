import numpy as np

# (eje horizontal, eje vertical) de cada vista en el mundo: 0 = x, 1 = y, 2 = z
VIEW_AXES = {"front": (0, 1), "back": (0, 1), "left": (2, 1), "right": (2, 1), "top": (0, 2), "bottom": (0, 2)}


def view_to_world(key, x, y, dims):
    """Punto de una vista (metros desde la esquina inferior izquierda del objeto en esa vista) -> mundo (x, y, z).
    'dims' = (ancho, alto, fondo). El frente del objeto mira a +z; el suelo es y = 0; el objeto está centrado en x y z."""
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
