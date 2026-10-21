"""Generación con JSON garantizado y decodificación por copia (prompt lookup): el texto que ya aparece en el contexto
(el JSON actual, ejemplos, lo ya escrito) se propone como borrador y se verifica de golpe, así un JSON largo que se parece a
uno existente se escribe a decenas de fichas por pasada. El resultado es idéntico al de generar ficha a ficha."""
import numpy as np

from app.ai.engine.jsonfsm import JsonPrefix

TOP_K = 48
DRAFT = 28           # fichas propuestas por pasada
NGRAM = 4            # fichas de contexto que deben coincidir para proponer una copia


class Cancelled(Exception):
    pass


def chat_prompt(tok, system, turns, assistant_prefix="", no_think=False):
    """ChatML. turns = [(rol, texto)...] con rol 'user'|'assistant'. Termina abierto en el turno del asistente."""
    parts = [f"<|im_start|>system\n{system}<|im_end|>\n"]
    for role, text in turns:
        parts.append(f"<|im_start|>{role}\n{text}<|im_end|>\n")
    parts.append("<|im_start|>assistant\n" + ("<think>\n\n</think>\n\n" if no_think else "") + assistant_prefix)
    return tok.encode("".join(parts))


def _find_draft(ids):
    """Fichas que siguieron la última vez que apareció el final actual del contexto (None si no hay coincidencia)."""
    if len(ids) < NGRAM + 2:
        return None
    arr = np.asarray(ids)
    tail = arr[-NGRAM:]
    cand = np.nonzero(arr[:-NGRAM] == tail[0])[0]
    for i in cand[::-1]:
        if i + NGRAM < len(arr) - NGRAM and np.array_equal(arr[i:i + NGRAM], tail):
            d = arr[i + NGRAM:i + NGRAM + DRAFT]
            if len(d):
                return [int(t) for t in d]
    return None


def generate_json(model, tok, prompt_ids, prefix="", max_tokens=1200, temperature=0.0, seed=0, on_text=None, cancel=None, use_copy=True, strict=True):
    """Continúa 'prompt_ids' hasta cerrar el objeto JSON raíz. 'prefix' es el texto ya incluido al final del prompt.
    Devuelve el texto JSON completo (prefix + lo generado)."""
    fsm = JsonPrefix()
    if prefix and not fsm.feed(prefix):
        raise ValueError("El prefijo inicial no es un JSON válido.")
    rng = np.random.default_rng(seed)
    ids = list(prompt_ids)
    text, n_gen = prefix, 0
    while n_gen < max_tokens:
        if cancel and cancel():
            raise Cancelled()
        if fsm.done:
            return text
        draft = _find_draft(ids) if (use_copy and temperature <= 0) else None
        if draft:
            logits = model.forward(ids + draft, len(draft) + 1)
            rows = [logits[i] for i in range(len(draft) + 1)]
        else:
            rows = [model.forward(ids)]
        for i, row in enumerate(rows):
            chosen = _pick(row, tok, fsm, temperature, rng)
            if chosen is None:
                raise ValueError("El modelo no encontró una continuación válida del JSON.")
            t_id, piece = chosen
            fsm.feed(piece)
            ids.append(t_id)
            text += piece
            n_gen += 1
            if on_text:
                on_text(piece)
            if fsm.done or not draft or i >= len(draft) or t_id != draft[i]:
                break
    if fsm.done or not strict:
        return text
    raise ValueError("La respuesta se cortó antes de completar el JSON (demasiado larga).")


def _pick(logits, tok, fsm, temperature, rng):
    for k in (TOP_K, len(logits)):
        k = min(k, len(logits))
        idx = np.argpartition(-logits, k - 1)[:k] if k < len(logits) else np.arange(len(logits))
        idx = idx[np.argsort(-logits[idx])]
        valid = []
        for i in idx:
            s = tok.text_of(int(i))
            if not s:
                continue
            c = fsm.clone()
            if c.feed(s):
                valid.append((int(i), s))
                if temperature <= 0 or len(valid) >= 8:
                    break
        if valid:
            if temperature <= 0 or len(valid) == 1:
                return valid[0]
            lg = np.array([logits[i] for i, _ in valid], np.float64) / temperature
            p = np.exp(lg - lg.max())
            return valid[int(rng.choice(len(valid), p=p / p.sum()))]
    return None
