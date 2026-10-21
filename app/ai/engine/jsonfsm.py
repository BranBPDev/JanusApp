"""Autómata incremental que acepta solo prefijos de JSON válido (compacto, sin espacios fuera de las cadenas).

Se usa para que el modelo no pueda escribir un carácter que rompa el JSON: se comprueban los candidatos antes de elegirlos."""

_WS = ""            # no se permiten espacios fuera de cadenas (JSON compacto: menos fichas y menos desvíos)
_HEX = set("0123456789abcdefABCDEF")
_DIGITS = set("0123456789")

# modos
VALUE, OBJ_FIRST, OBJ_KEY, COLON, AFTER, ARR_FIRST, STRING, NUMBER, LITERAL, DONE = range(10)


class JsonPrefix:
    __slots__ = ("stack", "mode", "key", "esc", "uni", "num", "lit")

    def __init__(self):
        self.stack = []             # '{' o '['
        self.mode = VALUE
        self.key = False            # la cadena actual es una clave
        self.esc = False
        self.uni = 0
        self.num = ""
        self.lit = ""

    def clone(self):
        c = JsonPrefix.__new__(JsonPrefix)
        c.stack, c.mode, c.key, c.esc, c.uni, c.num, c.lit = list(self.stack), self.mode, self.key, self.esc, self.uni, self.num, self.lit
        return c

    @property
    def done(self):
        return self.mode == DONE or (self.mode == NUMBER and not self.stack and self.num_ok())

    def num_ok(self):
        return bool(self.num) and self.num[-1] in _DIGITS

    def _end_value(self):
        self.mode = AFTER if self.stack else DONE

    def _start_value(self, c):
        if c == "{":
            self.stack.append("{")
            self.mode = OBJ_FIRST
        elif c == "[":
            self.stack.append("[")
            self.mode = ARR_FIRST
        elif c == '"':
            self.mode, self.key, self.esc, self.uni = STRING, False, False, 0
        elif c == "-" or c in _DIGITS:
            self.mode, self.num = NUMBER, c
        elif c in "tfn":
            self.mode, self.lit = LITERAL, {"t": "rue", "f": "alse", "n": "ull"}[c]
        else:
            return False
        return True

    def feed_char(self, c):
        m = self.mode
        if m == STRING:
            if self.uni:
                if c not in _HEX:
                    return False
                self.uni -= 1
            elif self.esc:
                if c == "u":
                    self.uni = 4
                elif c not in '"\\/bfnrt':
                    return False
                self.esc = False
            elif c == "\\":
                self.esc = True
            elif c == '"':
                if self.key:
                    self.mode = COLON
                else:
                    self._end_value()
            elif ord(c) < 0x20:
                return False
            return True
        if m == NUMBER:
            n = self.num
            if c in _DIGITS:
                if n in ("0", "-0"):
                    return False
                self.num = n + c
                return True
            if c == "." and n[-1] in _DIGITS and "." not in n and "e" not in n.lower():
                self.num = n + c
                return True
            if c in "eE" and n[-1] in _DIGITS and "e" not in n.lower():
                self.num = n + c
                return True
            if c in "+-" and n[-1] in "eE":
                self.num = n + c
                return True
            if not self.num_ok():
                return False
            self._end_value()          # el número terminó: este carácter pertenece a lo siguiente
            return self.feed_char(c) if self.mode != DONE else False
        if m == LITERAL:
            if c != self.lit[0]:
                return False
            self.lit = self.lit[1:]
            if not self.lit:
                self._end_value()
            return True
        if m == VALUE:
            if not self.stack and c != "{":
                return False           # la raíz es siempre un objeto
            return self._start_value(c)
        if m == OBJ_FIRST:
            if c == "}":
                self.stack.pop()
                self._end_value()
                return True
            if c == '"':
                self.mode, self.key, self.esc, self.uni = STRING, True, False, 0
                return True
            return False
        if m == OBJ_KEY:
            if c == '"':
                self.mode, self.key, self.esc, self.uni = STRING, True, False, 0
                return True
            return False
        if m == COLON:
            if c == ":":
                self.mode = VALUE
                return True
            return False
        if m == ARR_FIRST:
            if c == "]":
                self.stack.pop()
                self._end_value()
                return True
            self.mode = VALUE
            return self.feed_char(c)
        if m == AFTER:
            top = self.stack[-1]
            if c == ",":
                self.mode = OBJ_KEY if top == "{" else VALUE
                return True
            if (c == "}" and top == "{") or (c == "]" and top == "["):
                self.stack.pop()
                self._end_value()
                return True
            return False
        return False                    # DONE

    def feed(self, text):
        for c in text:
            if not self.feed_char(c):
                return False
        return True
