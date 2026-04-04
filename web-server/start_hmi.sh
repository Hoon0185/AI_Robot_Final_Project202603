#!/bin/bash

# Gilbot HMI Kiosk Launch Script (X11)
# --------------------------------------------------

# 1. Display Configuration
export DISPLAY=:0
xset s off
xset -dpms
xset s noblank

# 2. Cleanup existing sessions
killall -9 chromium-browser 2>/dev/null
killall -9 chromium 2>/dev/null

# 3. Launch Chromium in Kiosk Mode
# --window-size=800,480: Optimized for the 4.3" display
# --kiosk: Fullscreen without UI
# --noerrdialogs: Suppress error popups
# --incognito: Fresh start every time
# --disable-infobars: Remove top warnings

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
    "http://localhost:8000/hmi/" &

echo "🚀 Gilbot HMI Kiosk launched at http://localhost:8000/hmi/"
