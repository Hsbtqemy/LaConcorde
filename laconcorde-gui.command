#!/bin/bash
# Lance LaConcorde GUI (macOS)
# Cree un venv .venv si absent, puis installe les dependances GUI + formats.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1
export LC_ROOT="$SCRIPT_DIR"

PYTHON_BIN="python"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python3"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python introuvable. Installez Python ou activez votre venv."
  read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
  echo
  exit 1
fi

compute_hash() {
  "$PYTHON_BIN" - <<'PY'
import hashlib
import os
from pathlib import Path

root = Path(os.environ.get("LC_ROOT", "."))
paths = [root / "pyproject.toml", root / "requirements.txt"]
h = hashlib.sha256()
for p in paths:
    if p.exists():
        h.update(p.read_bytes())
print(h.hexdigest())
PY
}

if [ ! -d ".venv" ]; then
  echo "Creation du venv..."
  "$PYTHON_BIN" -m venv ".venv"
  if [ $? -ne 0 ]; then
    echo "Echec de creation du venv."
    read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
    echo
    exit 1
  fi
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
  echo "Installation des dependances..."
  python -m pip install --upgrade pip
  python -m pip install -e ".[gui,formats]"
  if [ $? -ne 0 ]; then
    echo "Echec d'installation des dependances."
    read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
    echo
    exit 1
  fi
  HASH_FILE=".venv/.laconcorde_gui_install_hash"
  CURRENT_HASH="$(compute_hash)"
  echo "$CURRENT_HASH" > "$HASH_FILE"
else
  # Activer le venv du projet s'il existe
  if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source ".venv/bin/activate"
    HASH_FILE=".venv/.laconcorde_gui_install_hash"
    CURRENT_HASH="$(compute_hash)"
    if [ ! -f "$HASH_FILE" ] || [ "$(cat "$HASH_FILE")" != "$CURRENT_HASH" ]; then
      echo "Mise a jour des dependances..."
      python -m pip install -e ".[gui,formats]"
      if [ $? -ne 0 ]; then
        echo "Echec d'installation des dependances."
        read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
        echo
        exit 1
      fi
      echo "$CURRENT_HASH" > "$HASH_FILE"
    fi
  fi
fi

python -m laconcorde_gui "$@"
status=$?
if [ $status -ne 0 ]; then
  echo
  echo "Si la GUI ne se lance pas, verifiez que PySide6/odfpy/xlrd sont installes:"
  echo "  pip install -e \".[gui,formats]\""
  read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
  echo
fi
exit $status
