#!/usr/bin/env python
"""
Build Windows installer using PyInstaller + Inno Setup.

Usage (on Windows):
    pip install -e ".[gui,formats]" pyinstaller
    python build_windows_installer.py

Requires Inno Setup (iscc.exe) installed and on PATH.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _read_version(root: Path) -> str:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return "0.1.0"
    try:
        import tomllib  # Python 3.11+

        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        return str(data.get("project", {}).get("version", "0.1.0"))
    except Exception:
        return "0.1.0"


def main() -> int:
    root = Path(__file__).parent.resolve()

    # Build the PyInstaller directory
    build_cmd = [sys.executable, str(root / "build_exe.py")]
    print("Exécution:", " ".join(build_cmd))
    result = subprocess.run(build_cmd, cwd=root)
    if result.returncode != 0:
        return result.returncode

    iscc = shutil.which("iscc")
    if not iscc:
        print("Inno Setup introuvable (iscc.exe). Installez-le puis relancez.")
        print(r"Vous pouvez aussi lancer: iscc /DAppVersion=0.1.0 installer\windows\laconcorde.iss")
        return 1

    version = _read_version(root)
    iss = root / "installer" / "windows" / "laconcorde.iss"
    cmd = [iscc, f"/DAppVersion={version}", str(iss)]
    print("Exécution:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=root)
    if result.returncode == 0:
        out_dir = root / "dist" / "installer"
        print(f"\nInstallateur créé dans: {out_dir}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
