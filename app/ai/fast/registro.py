"""Registro de la IA: cada petición y lo que respondió, en app/logs/ia/peticiones.jsonl (una línea JSON por evento).

Tipos de línea:
  peticion   -> id, hora, texto, estado (fichas del objeto), programa (lo que escribió la IA), ok/error, confianza, cambios, avisos, adjuntos, ms
  valoracion -> id, ok (true/false) y, si la IA falló, correccion (lo que el usuario quería)
  deshacer   -> id (el usuario deshizo ese cambio)
Se pasa este archivo para reentrenar la IA con los casos reales."""
import json
import threading
import time
import uuid

from app.utils.logger_util import get_logger
from app.utils.paths_util import IA_LOG_DIR, IA_LOG_PATH

log = get_logger("IA_REGISTRO")
_lock = threading.Lock()
MAX_BYTES = 8 * 1024 * 1024


def _write(entry: dict):
    try:
        with _lock:
            IA_LOG_DIR.mkdir(parents=True, exist_ok=True)
            if IA_LOG_PATH.exists() and IA_LOG_PATH.stat().st_size > MAX_BYTES:
                IA_LOG_PATH.replace(IA_LOG_PATH.with_suffix(f".{int(time.time())}.jsonl"))
            with IA_LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception as e:   # el registro nunca debe romper la aplicación
        log.warning(f"No se pudo escribir el registro de la IA: {e}")


def peticion(texto, estado, programa, ok, error="", confianza=None, cambios=(), avisos=(), adjuntos=(), ms=0.0, literales=None) -> str:
    id_ = uuid.uuid4().hex[:10]
    _write({"tipo": "peticion", "id": id_, "hora": time.strftime("%Y-%m-%d %H:%M:%S"), "texto": texto, "estado": list(estado),
            "programa": " ".join(programa), "ok": ok, "error": error, "confianza": None if confianza is None else round(float(confianza), 3),
            "cambios": list(cambios), "avisos": list(avisos), "adjuntos": list(adjuntos), "ms": round(ms, 1), "literales": literales or {}})
    return id_


def valoracion(id_, ok: bool, correccion: str = ""):
    _write({"tipo": "valoracion", "id": id_, "hora": time.strftime("%Y-%m-%d %H:%M:%S"), "ok": bool(ok), "correccion": correccion})


def deshacer(id_):
    _write({"tipo": "deshacer", "id": id_, "hora": time.strftime("%Y-%m-%d %H:%M:%S")})
