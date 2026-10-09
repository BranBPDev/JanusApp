from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class Part:
    """Pieza del objeto. Los vértices están en la pose de reposo (espacio del objeto)."""
    name: str
    vertices: np.ndarray               # (n,3) float32
    faces: np.ndarray                  # (m,3) int32
    normals: np.ndarray                # (n,3) float32
    uvs: Optional[np.ndarray] = None   # (n,2) float32
    parent: Optional[str] = None       # pieza de la que cuelga en la jerarquía
    origin: tuple = (0.0, 0.0, 0.0)    # pivote del nodo (bisagra, centro del botón...)
    axis: Optional[tuple] = None       # eje de giro de la apertura (regla de la mano derecha)
    open_angle: float = 0.0            # grados al abrir del todo


@dataclass
class Model:
    parts: list
    texture: Optional[np.ndarray] = None   # (h,w,4) uint8

    @property
    def triangles(self) -> int:
        return sum(len(p.faces) for p in self.parts)

    @property
    def vertex_count(self) -> int:
        return sum(len(p.vertices) for p in self.parts)

    @property
    def openable(self) -> bool:
        return any(p.axis is not None for p in self.parts)

    @property
    def size(self):
        v = np.concatenate([p.vertices for p in self.parts])
        return tuple((v.max(axis=0) - v.min(axis=0)).tolist())

    def scaled(self, sxz: float, sy: float) -> "Model":
        s = np.array([sxz, sy, sxz], np.float64)
        parts = []
        for p in self.parts:
            n = p.normals.astype(np.float64) / s
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
            parts.append(Part(p.name, (p.vertices * s).astype(np.float32), p.faces, n.astype(np.float32), p.uvs,
                              p.parent, tuple((np.array(p.origin) * s).tolist()), p.axis, p.open_angle))
        return Model(parts, self.texture)
