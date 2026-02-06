#!/usr/bin/env python
"""
Script de build pour créer un exécutable Windows autonome (LaConcorde GUI).

Usage:
    pip install -e ".[gui]" pyinstaller
    python build_exe.py

Le .exe et les DLL seront dans dist/laconcorde_gui/
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).parent.resolve()
    src = root / "src"

    # PyInstaller en mode --onedir (plus fiable pour Qt6/PySide6 que --onefile)
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=laconcorde_gui",
        "--windowed",  # Pas de console
        "--onedir",  # Dossier avec exe + DLL (recommandé pour Qt6)
        "--clean",
        "--noconfirm",
        # Chemins à inclure
        f"--paths={src}",
        # Point d'entrée
        str(root / "src" / "laconcorde_gui" / "app.py"),
        # Données optionnelles (icône, etc.)
        # "--icon=resources/icon.ico",
        # Exclusions pour réduire la taille
        "--exclude-module=tkinter",
        "--exclude-module=matplotlib",
        "--exclude-module=scipy",
        "--exclude-module=numpy.testing",
    ]

    print("Exécution:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=root)
    if result.returncode == 0:
        print("\nBuild reussi. Executable dans: dist/laconcorde_gui/laconcorde_gui.exe")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
