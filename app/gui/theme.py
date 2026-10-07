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
    "accent_hover": "#7C7FF5",
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


QLabel#Section { color: $muted; font-size: 11px; font-weight: 600; }
QLabel#Warn { color: $warning; }
QLabel#Thumb { background: $elevated; border: 1px solid $border; border-radius: 8px; }

QPushButton { background: $elevated; border: 1px solid $border; border-radius: 8px; padding: 7px 14px; color: $text; }
QPushButton:hover { border-color: $accent; }
QPushButton:disabled { color: $disabled; border-color: $border; }
QPushButton#Primary { background: $accent; border: none; color: white; font-weight: 600; padding: 11px 16px; }
QPushButton#Primary:hover { background: $accent_hover; }
QPushButton#Primary:disabled { background: $elevated; color: $disabled; }
QPushButton#Seg { padding: 6px 14px; border-radius: 6px; }
QPushButton#Seg:checked { background: $accent_soft; border-color: $accent; font-weight: 600; }

QLineEdit, QSpinBox, QDoubleSpinBox { background: $elevated; border: 1px solid $border; border-radius: 6px; padding: 6px 8px; selection-background-color: $accent; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: $accent; }

QSlider::groove:horizontal { height: 4px; background: $elevated; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QSlider::handle:horizontal { background: $text; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }

QCheckBox { spacing: 8px; }
QScrollArea { background: transparent; border: none; }

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
