def invoke_progress(callback, fraction: float, message: str = ""):
    """Notifica progreso (0.0 - 1.0) sin que un fallo del callback rompa el proceso."""
    if callback is None:
        return
    try:
        callback(max(0.0, min(1.0, fraction)), message)
    except Exception:
        pass
