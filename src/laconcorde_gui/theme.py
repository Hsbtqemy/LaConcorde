"""Gestion simple des thèmes UI."""

from __future__ import annotations

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"


def normalize_theme_mode(mode: str | None) -> str:
    if mode in (THEME_LIGHT, THEME_DARK, THEME_SYSTEM):
        return mode
    return THEME_SYSTEM


def is_dark_mode(mode: str | None) -> bool:
    mode = normalize_theme_mode(mode)
    if mode == THEME_DARK:
        return True
    if mode == THEME_LIGHT:
        return False
    app = QApplication.instance()
    palette = app.palette() if app is not None else QPalette()
    base = palette.color(QPalette.ColorRole.Window)
    return base.lightness() < 128


def build_app_qss(dark: bool) -> str:
    if dark:
        return (
            "QWidget { background: #2f2f2f; color: #f0f0f0; }"
            "QGroupBox { background: #3a3a3a; border: 1px solid #555; margin-top: 12px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #f0f0f0; }"
            "QFrame { background: #3a3a3a; }"
            "QPushButton, QToolButton { background: #444; color: #f0f0f0; border: 1px solid #666; padding: 4px 8px; }"
            "QPushButton:hover, QToolButton:hover { background: #505050; }"
            "QLineEdit, QComboBox, QSpinBox, QTextEdit, QListWidget, QTableView, QTableWidget {"
            " background: #2b2b2b; color: #f0f0f0; border: 1px solid #666; }"
            "QComboBox QAbstractItemView { background: #2b2b2b; color: #f0f0f0; }"
            "QListWidget::item:selected { background: #3a5a8a; color: #ffffff; }"
            "QTableWidget::item:selected, QTableView::item:selected { background: #3a5a8a; color: #ffffff; }"
            "QHeaderView::section { background: #404040; color: #f0f0f0; }"
            "QTabBar::tab { background: #444; color: #f0f0f0; border: 1px solid #666; padding: 4px 8px; }"
            "QTabBar::tab:selected { background: #505050; }"
        )
    return (
        "QWidget { background: #efefef; color: #111111; }"
        "QGroupBox { background: #f7f7f7; border: 1px solid #d6d6d6; margin-top: 12px; }"
        "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #111111; }"
        "QFrame { background: #f7f7f7; }"
        "QPushButton, QToolButton { background: #efefef; color: #111111; border: 1px solid #c9c9c9; padding: 4px 8px; }"
        "QPushButton:hover, QToolButton:hover { background: #e6e6e6; }"
        "QLineEdit, QComboBox, QSpinBox, QTextEdit, QListWidget, QTableView, QTableWidget {"
        " background: #ffffff; color: #111111; border: 1px solid #cfcfcf; }"
        "QComboBox QAbstractItemView { background: #ffffff; color: #111111; }"
        "QListWidget::item:selected { background: #cfe3ff; color: #111111; }"
        "QTableWidget::item:selected, QTableView::item:selected { background: #cfe3ff; color: #111111; }"
        "QHeaderView::section { background: #f2f2f2; color: #111111; }"
        "QTabBar::tab { background: #e7e7e7; color: #111111; border: 1px solid #c9c9c9; padding: 4px 8px; }"
        "QTabBar::tab:selected { background: #f2f2f2; }"
    )
