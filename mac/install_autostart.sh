#!/bin/sh
# Installs a LaunchAgent that starts blur_mac.py at login.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python3)"
PLIST="$HOME/Library/LaunchAgents/com.autoblur.mac.plist"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.autoblur.mac</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>$DIR/blur_mac.py</string></array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>RunAtLoad</key><true/>
</dict>
</plist>
EOF
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Installed: $PLIST"
echo "Remove with: launchctl unload \"$PLIST\" && rm \"$PLIST\""
