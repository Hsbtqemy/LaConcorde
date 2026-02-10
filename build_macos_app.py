#!/usr/bin/env python
"""
Build macOS .app bundle using PyInstaller.

Usage (on macOS):
    pip install -e ".[gui]" pyinstaller
    python build_macos_app.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).parent.resolve()
    src = root / "src"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=LaConcorde",
        "--windowed",
        "--onedir",
        "--clean",
        "--noconfirm",
        f"--paths={src}",
        "--osx-bundle-identifier=org.laconcorde.gui",
        str(root / "src" / "laconcorde_gui" / "app.py"),
        "--exclude-module=tkinter",
        "--exclude-module=matplotlib",
        "--exclude-module=scipy",
        "--exclude-module=numpy.testing",
    ]

    print("Exécution:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=root)
    if result.returncode == 0:
        print("\nBuild reussi. App dans: dist/LaConcorde.app")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
