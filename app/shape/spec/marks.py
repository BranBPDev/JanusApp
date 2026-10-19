from dataclasses import dataclass, field


@dataclass
class Marks:
    """Marcas del objeto ya interpretadas, por vista (claves front, back, left, right, top, bottom); metros desde la
    esquina inferior izquierda del objeto en esa vista."""
    cut: dict = field(default_factory=dict)         # [(a, b)]: líneas de corte
    move: dict = field(default_factory=dict)        # [punto]: lado que se mueve
    hinge: dict = field(default_factory=dict)       # [punto]: bisagra
    button: dict = field(default_factory=dict)      # [(centro, radio)]
    footprints: dict = field(default_factory=dict)  # máscara booleana (alto, ancho) de lo que sobresale, del tamaño de la vista
    joints: dict = field(default_factory=dict)      # [{'id', 'parent', 'x_m', 'y_m'}]

    def to_dict(self) -> dict:
        """Resumen serializable (para el manifest del proyecto)."""
        out = {k: _plain(getattr(self, k)) for k in ("cut", "move", "hinge", "button", "joints") if getattr(self, k)}
        if self.footprints:
            out["footprints"] = sorted(self.footprints)
        return out


def _plain(x):
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    return round(float(x), 5) if isinstance(x, float) else x
