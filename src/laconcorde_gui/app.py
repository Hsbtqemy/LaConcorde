"""Point d'entrée de l'application GUI LaConcorde."""

from __future__ import annotations

import sys

# Import pandas avant PySide6 pour éviter le conflit shiboken/six
# (AttributeError: '_SixMetaPathImporter' object has no attribute '_path')
import pandas  # noqa: F401

from PySide6.QtWidgets import QApplication

from laconcorde_gui.main_window import MainWindow


def main() -> int:
    """Lance l'application GUI."""
    app = QApplication(sys.argv)
    app.setApplicationName("LaConcorde")
    app.setOrganizationName("LaConcorde")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
