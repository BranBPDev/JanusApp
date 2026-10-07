from string import Template
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

COLORS = {
    "bg": "#0E1016",
    "surface": "#151823",
    "elevated": "#1D2130",
    "border": "#262B3D",
    "hover": "#1B1F2E",
    "text": "#E7E9F0",
    "muted": "#8A90A6",
    "disabled": "#4B5066",
    "accent": "#6366F1",
    "accent_soft": "rgba(99, 102, 241, 0.18)",
    "success": "#34D399",
    "warning": "#FBBF24",
}

_QSS = Template("""
* { font-family: "Segoe UI", "Inter", sans-serif; font-size: 13px; }
QMainWindow, QWidget#Root { background: $bg; }
QLabel { color: $text; background: transparent; }
QLabel#Title { font-size: 26px; font-weight: 600; }
QLabel#Subtitle { color: $muted; font-size: 14px; }
QLabel#Muted { color: $muted; }
QLabel#CardTitle { color: $muted; font-size: 12px; }
QLabel#CardValue { font-size: 20px; font-weight: 600; }
QLabel#Brand { font-size: 16px; font-weight: 600; }

QFrame#Sidebar { background: $surface; border: none; border-right: 1px solid $border; }
QFrame#Card { background: $surface; border: 1px solid $border; border-radius: 12px; }

QPushButton#NavButton {
    text-align: left; padding: 10px 14px; border: none; border-radius: 8px;
    color: $muted; background: transparent; font-size: 13px;
}
QPushButton#NavButton:hover { background: $hover; color: $text; }
QPushButton#NavButton:checked { background: $accent_soft; color: $text; font-weight: 600; }
QPushButton#NavButton:disabled { color: $disabled; }

QProgressBar { background: $elevated; border: none; border-radius: 3px; min-height: 6px; max-height: 6px; color: transparent; }
QProgressBar::chunk { background: $accent; border-radius: 3px; }

QFrame#UpdateCard { background: $surface; border: 1px solid $border; border-radius: 16px; }

QStatusBar { background: $surface; color: $muted; border-top: 1px solid $border; }
QStatusBar::item { border: none; }
QToolTip { background: $elevated; color: $text; border: 1px solid $border; padding: 4px 8px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: $border; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $disabled; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
""")


def apply_theme(app: QApplication):
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))

    palette = QPalette()
    for role, key in (
        (QPalette.Window, "bg"), (QPalette.Base, "surface"), (QPalette.AlternateBase, "elevated"),
        (QPalette.Button, "elevated"), (QPalette.ToolTipBase, "elevated"), (QPalette.WindowText, "text"),
        (QPalette.Text, "text"), (QPalette.ButtonText, "text"), (QPalette.ToolTipText, "text"),
        (QPalette.Highlight, "accent"), (QPalette.HighlightedText, "text"),
    ):
        palette.setColor(role, QColor(COLORS[key]))
    palette.setColor(QPalette.PlaceholderText, QColor(COLORS["muted"]))
    app.setPalette(palette)
    app.setStyleSheet(_QSS.substitute(COLORS))
