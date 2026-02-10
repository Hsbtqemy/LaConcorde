#!/bin/bash
# Build a .dmg from dist/LaConcorde.app (macOS)
# Requires: create-dmg (brew install create-dmg)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_PATH="$ROOT_DIR/dist/LaConcorde.app"
OUT_DIR="$ROOT_DIR/dist"
OUT_DMG="$OUT_DIR/LaConcorde.dmg"

if [ ! -d "$APP_PATH" ]; then
  echo "App introuvable: $APP_PATH"
  echo "Lancez d'abord: python build_macos_app.py"
  exit 1
fi

if ! command -v create-dmg >/dev/null 2>&1; then
  echo "create-dmg introuvable. Installez-le avec:"
  echo "  brew install create-dmg"
  exit 1
fi

rm -f "$OUT_DMG"

create-dmg \
  --volname "LaConcorde" \
  --window-size 600 400 \
  --icon-size 120 \
  --icon "LaConcorde.app" 160 200 \
  --app-drop-link 440 200 \
  "$OUT_DMG" \
  "$OUT_DIR"

echo "DMG genere: $OUT_DMG"
