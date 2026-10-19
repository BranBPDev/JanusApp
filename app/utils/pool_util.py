import os
from concurrent.futures import ThreadPoolExecutor

WORKERS = min(8, os.cpu_count() or 2)


def parallel_map(fn, items, workers: int = None) -> list:
    """fn(item) para cada elemento, en un pool de hilos, conservando el orden. Con un solo elemento no crea hilos.
    (numpy y Pillow sueltan el GIL en las operaciones grandes, así que el dibujo y la E/S sí se solapan)."""
    items = list(items)
    if len(items) <= 1:
        return [fn(i) for i in items]
    with ThreadPoolExecutor(min(workers or WORKERS, len(items))) as pool:
        return list(pool.map(fn, items))


def parallel_dict(tasks: dict, workers: int = None) -> dict:
    """{clave: función sin argumentos} -> {clave: resultado}, ejecutadas en paralelo."""
    keys = list(tasks)
    return dict(zip(keys, parallel_map(lambda k: tasks[k](), keys, workers)))
