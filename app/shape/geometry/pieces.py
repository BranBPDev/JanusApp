LOOSE_NAMES = {"fixed": "mitad_a", "movable": "mitad_b"}     # nombres de las dos mitades cuando se separan del todo


def bbox_centre(vertices) -> tuple:
    """Centro de la caja que envuelve los puntos."""
    return tuple(float(c) for c in (vertices.min(axis=0) + vertices.max(axis=0)) / 2)


def part_name(name: str, loose: bool) -> str:
    return LOOSE_NAMES.get(name, name) if loose else name


def loose_names(count: int, names=None) -> list:
    """Nombre de cada pieza suelta: los dados, 'mitad_a'/'mitad_b' si son dos o 'pieza_1', 'pieza_2'… si son más."""
    if names:
        return list(names)
    return list(LOOSE_NAMES.values()) if count == 2 else [f"pieza_{i + 1}" for i in range(count)]


def node_props(vertices, loose: bool, hinge=None) -> dict:
    """Argumentos de nodo de una pieza al crear su Part.
    loose: objeto suelto, sin padre ni bisagra: gira sobre el centro de su caja.
    hinge = (origen, eje, grados): pieza móvil. Sin ninguno: pieza fija (o única)."""
    if loose:
        return {"origin": bbox_centre(vertices), "independent": True}
    if hinge is not None:
        origin, axis, angle = hinge
        return {"origin": origin, "axis": axis, "open_angle": angle}
    return {}
