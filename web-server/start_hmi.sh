#!/bin/bash

# Gilbot HMI Kiosk Launch Script (X11 + xinit Fallback)
# --------------------------------------------------

# 1. Cleanup existing sessions and stale lock files
rm -rf /tmp/chromium-hmi 2>/dev/null
killall -9 chromium-browser 2>/dev/null
killall -9 chromium 2>/dev/null

# 2. X Server Lifecycle Management
if [[ -z "$DISPLAY" ]]; then
    echo "⚠️ No X server detected. Attempting to start with xinit..."
    if command -v xinit >/dev/null 2>&1; then
        export DISPLAY=:0
        exec xinit "$0" -- :0
    else
        echo "❌ xinit not found. Please install it with: sudo apt install xinit"
        exit 1
    fi
fi

# 3. Environment & Display Configuration (Permission Fix)
export DISPLAY=:0
export XDG_RUNTIME_DIR="/tmp/runtime-hmi-$(whoami)"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

xset s off 2>/dev/null
xset -dpms 2>/dev/null
xset s noblank 2>/dev/null

# 4. Launch Chromium in Kiosk Mode (Dynamic IP Detection)
SERVER_IP=$(hostname -I | awk '{print $1}')
TARGET_URL="http://${SERVER_IP}/hmi/"

# 보안 경고 무시 및 안전한 오리진 강제 지정
SECURITY_FLAGS="--ignore-certificate-errors --allow-running-insecure-content --unsafely-treat-insecure-origin-as-secure=$TARGET_URL"

echo "🚀 Gilbot HMI Kiosk launching at $TARGET_URL (with Security Bypass)"

chromium-browser \
    --kiosk \
    $SECURITY_FLAGS \
    --noerrdialogs \
    --disable-infobars \
    --window-size=800,480 \
    --window-position=0,0 \
    --incognito \
    --autoplay-policy=no-user-gesture-required \
    --check-for-update-interval=31536000 \
    --disable-pinch \
    --overscroll-history-navigation=0 \
    --no-first-run \
    --no-sandbox \
    --no-default-browser-check \
    --user-data-dir=/tmp/chromium-hmi \
    "$TARGET_URL"
