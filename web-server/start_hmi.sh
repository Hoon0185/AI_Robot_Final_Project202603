#!/bin/bash

# Gilbot HMI Kiosk Launch Script (X11 + xinit Fallback)
# --------------------------------------------------

# 1. Cleanup existing sessions and stale lock files
# This prevents "Permission denied" on SingletonLock common in mixed sudo/non-sudo runs
rm -rf /tmp/chromium-hmi 2>/dev/null
killall -9 chromium-browser 2>/dev/null
killall -9 chromium 2>/dev/null

# 2. X Server Lifecycle Management
# If DISPLAY is not set, we are likely in a CLI console. Use xinit to start X.
if [[ -z "$DISPLAY" ]]; then
    echo "⚠️ No X server detected. Attempting to start with xinit..."
    if command -v xinit >/dev/null 2>&1; then
        export DISPLAY=:0
        # Re-run this script within an X session.
        # We use the absolute path or the current script's relative path.
        exec xinit "$0" -- :0
    else
        echo "❌ xinit not found. Please install it with: sudo apt install xinit"
        exit 1
    fi
fi

# 3. Environment & Display Configuration
export DISPLAY=:0

# Prevent Chromium from failing to create a directory in /run/user/0 when run via sudo
export XDG_RUNTIME_DIR=/tmp/runtime-hmi
mkdir -p $XDG_RUNTIME_DIR
chmod 700 $XDG_RUNTIME_DIR

# Disable screensavers and power management
xset s off 2>/dev/null
xset -dpms 2>/dev/null
xset s noblank 2>/dev/null

# 4. Launch Chromium in Kiosk Mode (16.184.56.119)
TARGET_URL="http://16.184.56.119:8000/hmi/"

echo "🚀 Gilbot HMI Kiosk launching at $TARGET_URL"

chromium-browser \
    --kiosk \
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
