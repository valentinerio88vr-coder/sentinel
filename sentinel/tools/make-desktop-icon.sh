#!/usr/bin/env bash
# Creates a macOS .app bundle or a Linux .desktop launcher for Sentinel.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ICON="$ROOT/assets/sentinel.png"

if [ ! -f "$ICON" ]; then
  echo "icon missing — run: python3 tools/make_icon.py"
  exit 1
fi
chmod +x "$ROOT/run.sh"

if [ "$(uname -s)" = "Darwin" ]; then
  APP="$HOME/Desktop/Sentinel.app"
  rm -rf "$APP"
  mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
  cp "$ICON" "$APP/Contents/Resources/sentinel.png"

  cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Sentinel</string>
  <key>CFBundleDisplayName</key><string>Sentinel</string>
  <key>CFBundleIdentifier</key><string>local.sentinel.family</string>
  <key>CFBundleVersion</key><string>2.0.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleIconFile</key><string>sentinel.png</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict></plist>
PLIST

  cat > "$APP/Contents/MacOS/Sentinel" <<LAUNCH
#!/bin/bash
open -a Terminal "$ROOT/run.sh"
LAUNCH
  chmod +x "$APP/Contents/MacOS/Sentinel"
  echo "Created $APP"

else
  DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
  mkdir -p "$DESKTOP_DIR" "$HOME/.local/share/icons"
  cp "$ICON" "$HOME/.local/share/icons/sentinel.png"
  ENTRY="$DESKTOP_DIR/sentinel.desktop"
  cat > "$ENTRY" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Sentinel
Comment=Family safety console
Exec=bash -c 'cd "$ROOT" && ./run.sh'
Icon=$HOME/.local/share/icons/sentinel.png
Terminal=true
Categories=Utility;Security;
DESKTOP
  chmod +x "$ENTRY"
  echo "Created $ENTRY"
fi
