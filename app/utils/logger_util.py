import logging
import sys
from logging.handlers import RotatingFileHandler
from app.utils.paths_util import MAIN_LOG_PATH, IS_FROZEN

_ROOT = "janus"
_configured = False


def _configure():
    global _configured
    if _configured:
        return
    root = logging.getLogger(_ROOT)
    root.setLevel(logging.DEBUG)
    root.propagate = False
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    file_handler = RotatingFileHandler(MAIN_LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    if not IS_FROZEN:  # el .exe es sin consola
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        root.addHandler(console)
    _configured = True


def get_logger(name: str = "SYSTEM") -> logging.Logger:
    _configure()
    return logging.getLogger(f"{_ROOT}.{name.split('.')[-1]}")


def install_excepthook():
    log = get_logger("CRASH")

    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("Excepción no capturada", exc_info=(exc_type, exc, tb))

    sys.excepthook = hook


def shutdown_logs():
    logging.shutdown()
