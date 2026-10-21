"""Asistente de JSON: la IA escribe el JSON COMPLETO del objeto (nuevo o modificado); aquí se prepara lo que ve (objeto
actual, imágenes, archivos de ejemplo), se valida lo que escribe, se le devuelven los errores y se le pide una revisión."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.ai.assistant import escena, vision
from app.ai.engine.generate import Cancelled, chat_prompt, generate_json
from app.ai.engine.model import LlamaLike
from app.ai.engine.tokenizer import Tokenizer
from app.shape.spec.schema import SpecError
from app.utils.logger_util import get_logger

log = get_logger(__name__)
MAX_ATTEMPTS = 3
MAX_TOKENS = 7000
MAX_CTX = 16384
PREFIX = '{"formato":"janus.objeto/1","nombre":"'
from app.ai.assistant import ejemplos as _ej
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}
TEXT_EXT = {".json", ".txt", ".md", ".csv"}
TEXT_LIMIT = 6000

COLORS = {"rojo": "#d62d20", "azul": "#2f6fd0", "verde": "#2f9e44", "amarillo": "#f2c230", "naranja": "#f08a24", "morado": "#7a3fb0",
          "violeta": "#7a3fb0", "rosa": "#f080b0", "marron": "#7a4a2a", "marrón": "#7a4a2a", "negro": "#111111", "blanco": "#f5f5f5",
          "gris": "#8a8a90", "dorado": "#d9a928", "oro": "#d9a928", "plateado": "#c0c4cc", "plata": "#c0c4cc", "turquesa": "#1fb5b5",
          "cian": "#15eeee", "beige": "#e8dcc0", "celeste": "#8fd0f0"}
COLORS.update({k[:-1] + "a": v for k, v in list(COLORS.items()) if k.endswith("o") and k != "oro"})

SYSTEM = """Eres el generador de JSON de JanusApp. Respondes SOLO con el JSON completo de un objeto 3D (formato "janus.objeto/1"), sin texto ni explicaciones. Si te doy un objeto actual, devuelves el objeto completo con los cambios pedidos. El "interior" actual se conserva solo si no lo escribes.
Medidas en METROS. Colores "#rrggbb". Claves del JSON:
formato, nombre, medidas_m{ancho,alto,fondo}, texturas{nombre:{color}|{degradado:{desde,hasta,angulo}}}, sombreado{luz,base,intensidad}, contorno{color,grosor_m},
vistas{frente,detras,izquierda,derecha,arriba,abajo:{capas:[...]}} (frente y una lateral obligatorias), relieves[...], marcas{...}, interior{tapa|base:{lado_m,circular,capas}}.
Capas (se pintan en orden): {"textura","forma","silueta","sombrear","recorte","borde"} con forma: circulo{centro,radio} | elipse{centro,radios[rx,ry]} | rect{esquina,tamano[ancho,alto],radio_esquina} | poligono{puntos} | linea{puntos,grosor}. "silueta":true = la capa forma la silueta (lo demás se pinta dentro). "sombrear":true = relieve de esfera. "recorte":[x0,y0,x1,y1] limita la capa a esa caja.
Coordenadas de cada vista: origen abajo a la izquierda del cuadro del objeto. frente/detras: x=ancho,y=alto. izquierda/derecha: x=fondo,y=alto. arriba/abajo: x=ancho,y=fondo.
Una esfera de diámetro D: medidas D×D×D, en cada vista un círculo centro [D/2,D/2] radio D/2 con silueta y sombrear. Para que se abra: marcas.corte [{"vista":"derecha","linea":[[0,D/2],[D,D/2]]}], marcas.mueve (punto de la tapa), marcas.bisagra (punto del pivote), marcas.boton [{"vista":"frente","centro":[D/2,D/2],"radio":r}]. La tapa es la mitad de arriba (capa con recorte desde y=D/2). Banda = rect centrado en y=D/2 en todas las vistas laterales; botón = círculo centrado en la vista frente.
Relieves (piezas que sobresalen de una esfera de radio radio_m, centrada en la caja y apoyada en el suelo; ancho/fondo de medidas_m deben dar margen):
 franja{inclinacion_grados,ancho_m,sobresale_m,margen_m,simetrica} · cadena{eje[x,y,z],radio_aro_m,eslabones,largo_m,ancho_m,grosor_m,hueco{eje,radio_m}} · cuerda{eje,radio_aro_m,hebras,vueltas,grosor_m}
 pieza{forma:esfera|elipsoide|caja|cilindro|cono|toro,lat_grados,lon_grados(0=frente),tamano_m[este,norte,altura],giro_grados,hunde_m,copias,paso_grados} · malla{vertices[[este,norte,fuera]],caras[[i,j,k]],lat_grados,lon_grados,giro_grados,hunde_m,copias,paso_grados} para piezas propias.
 Todos llevan "tipo","textura" (nombre de una textura) y "radio_m".
Huesos (opcional): marcas.huesos [{"id":0,"padre":null,"frente":[x,y],"derecha":[z,y]}].
Ejemplo 1 (esfera simple, sin nada más):
%s
Ejemplo 2 (esfera que se abre: tapa, banda y botón):
%s"""


def compact(data, keep_interior=True) -> str:
    """JSON en una línea con los decimales recortados (menos fichas); sin 'interior' si keep_interior es False."""
    def rnd(v):
        if isinstance(v, float):
            return round(v, 4)
        if isinstance(v, list):
            return [rnd(x) for x in v]
        if isinstance(v, dict):
            return {k: rnd(x) for k, x in v.items()}
        return v
    d = {k: v for k, v in data.items() if keep_interior or k != "interior"}
    return json.dumps(rnd(d), separators=(",", ":"), ensure_ascii=False)


def _system() -> str:
    ex = [compact(_ej.ejemplo(n)) for n in ("esfera_simple", "esfera_banda_boton")]
    return SYSTEM % tuple(ex)


@dataclass
class Resultado:
    spec: dict
    cambios: list
    informe: str
    avisos: list = field(default_factory=list)
    intentos: int = 1
    revisado: str = ""
    salida: str = ""


def read_attachment(path) -> tuple:
    """(nombre, texto que ve la IA) de una imagen o un archivo de texto."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in IMAGE_EXT:
        return p.name, "[imagen] " + vision.analyze(p)
    if ext in TEXT_EXT:
        text = p.read_text(encoding="utf-8", errors="replace")
        if ext == ".json":
            try:
                data = json.loads(text)
                if isinstance(data, dict) and data.get("formato") == "janus.objeto/1":
                    return p.name, "[objeto de ejemplo] " + compact(data, keep_interior=False)
                return p.name, compact(data) if isinstance(data, dict) else text[:TEXT_LIMIT]
            except json.JSONDecodeError:
                pass
        return p.name, text[:TEXT_LIMIT]
    raise SpecError(f"No sé leer archivos «{ext}». Adjunta imágenes (png, jpg...), JSON o texto.")


def hint_colors(text: str) -> str:
    def sub(m):
        return f"{m.group(0)} ({COLORS[m.group(0).lower()]})"
    return re.sub(r"\b(" + "|".join(sorted(COLORS, key=len, reverse=True)) + r")\b(?!\s*\(#)", sub, text, flags=re.I)


def diff(a, b, path="", out=None, limit=14):
    """Lista breve de diferencias entre dos JSON (rutas con puntos)."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a.keys() | b.keys():
            if k not in a:
                out.append(f"añadido {path}{k}")
            elif k not in b:
                out.append(f"quitado {path}{k}")
            else:
                diff(a[k], b[k], f"{path}{k}.", out, limit)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}{i}.", out, limit)
    elif a != b:
        sa, sb = json.dumps(a, ensure_ascii=False), json.dumps(b, ensure_ascii=False)
        out.append(f"{path[:-1]}: {sa[:40]} → {sb[:40]}")
    return out


class Asistente:
    def __init__(self, model_path, max_ctx=MAX_CTX, progress=None):
        self.model = LlamaLike(model_path, max_ctx=max_ctx, progress=progress)
        self.tok = Tokenizer(self.model.meta)
        self.no_think = self.model.arch == "qwen3"
        self.system = _system()

    # ---- una generación completa de JSON ----
    def _write(self, turns, on_text, cancel):
        prompt = chat_prompt(self.tok, self.system, turns, PREFIX, self.no_think)
        if len(prompt) + 800 > self.model.max_ctx:
            raise SpecError("Lo que le envías es demasiado largo para el contexto del modelo: adjunta menos archivos o un objeto más pequeño.")
        budget = min(MAX_TOKENS, self.model.max_ctx - len(prompt) - 8)
        return generate_json(self.model, self.tok, prompt, PREFIX, budget, 0.0, 0, on_text, cancel)

    @staticmethod
    def _user_turn(request, spec, attachments):
        parts = ["Objeto actual: " + (compact(spec, keep_interior=False) + ("\n(Tiene interior: se conserva si no lo escribes.)" if spec.get("interior") else "")
                                      if spec else "ninguno todavía.")]
        for name, text in attachments:
            parts.append(f"Adjunto «{name}»:\n{text}")
        parts.append(f"Petición: {request}")
        return "\n\n".join(parts)

    def _accept(self, out, spec):
        data = json.loads(out)
        if spec.get("interior") and "interior" not in data:
            data["interior"] = spec["interior"]
        report = escena.report(data)          # valida y calcula: lanza SpecError si algo falla
        return data, report

    def pedir(self, text, spec, adjuntos=(), on_text=None, cancel=None, revisar=True, on_stage=None) -> Resultado:
        stage = on_stage or (lambda s: None)
        attachments = [read_attachment(a) if not isinstance(a, tuple) else a for a in adjuntos]
        request = hint_colors(text)
        turns = [("user", self._user_turn(request, spec or {}, attachments))]
        extra, last_err = [], ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            stage(f"Escribiendo el JSON (intento {attempt})...")
            out = ""
            try:
                out = self._write(turns + extra, on_text, cancel)
                data, report = self._accept(out, spec or {})
            except Cancelled:
                raise
            except (ValueError, SpecError) as e:       # JSON cortado, no válido para JanusApp, etc.
                last_err = str(e) if isinstance(e, SpecError) else f"El JSON no se pudo completar o leer: {e}"
                log.info("Intento %d rechazado: %s", attempt, last_err)
                if isinstance(e, SpecError) and str(e).startswith("Lo que le envías"):
                    raise
                extra = ([("assistant", out)] if out else []) + [("user", f"Error: {last_err}\nDevuelve de nuevo el JSON completo corregido.")]
                continue
            problems = escena.check_request(text, data)
            revised = ""
            if revisar:
                stage("Revisando el resultado...")
                try:
                    data, report, problems, revised = self._review(turns, out, data, report, problems, text, spec or {}, on_text, cancel)
                except Cancelled:
                    raise
                except Exception as e:
                    log.info("Revisión descartada: %s", e)
            changes = diff(spec, data) if spec else [f"objeto nuevo «{data.get('nombre')}»"]
            return Resultado(data, changes, report, problems, attempt, revised, out)
        raise SpecError(f"No conseguí un JSON válido tras {MAX_ATTEMPTS} intentos. Último problema: {last_err}")

    def _review(self, turns, out, data, report, problems, request, spec, on_text, cancel):
        """Le enseña a la IA el informe medido de lo que escribió; si lo corrige y sigue siendo válido, se adopta."""
        notes = "\n".join(problems) if problems else "ninguna"
        ask = (f"Revisa tu resultado contra la petición: «{request}».\nInforme medido del objeto:\n{report}\nComprobaciones automáticas fallidas: {notes}\n"
               "Si algo no coincide con lo pedido, devuelve el JSON completo corregido; si todo está bien, devuelve exactamente el mismo JSON.")
        new_out = self._write(turns + [("assistant", out), ("user", ask)], on_text, cancel)
        new, new_report = self._accept(new_out, spec)
        if compact(new) == compact(data):
            return data, report, problems, "comprobado: sin cambios"
        return new, new_report, escena.check_request(request, new), "corregido en la revisión"
