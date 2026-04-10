#!/bin/bash

# Gilbot HMI Kiosk Stop Script
# ----------------------------

echo "🛑 Stopping Gilbot HMI Kiosk..."

# 1. Kill Chromium processes (Snap and regular)
# Snap version uses a long path, so -f helps.
sudo pkill -9 -f "chromium-browser" 2>/dev/null
sudo pkill -9 -f "snap.chromium" 2>/dev/null
sudo pkill -9 -i "chromium" 2>/dev/null

# 2. Kill xinit and X server if managed by start_hmi.sh
sudo pkill -9 -f "xinit" 2>/dev/null
sudo pkill -9 -f "Xorg" 2>/dev/null

# 3. Cleanup temp files and locks
sudo rm -rf /tmp/chromium-hmi 2>/dev/null
sudo rm -f /tmp/.X0-lock 2>/dev/null
sudo rm -rf /tmp/runtime-hmi-* 2>/dev/null

echo "✅ HMI Processes cleared and X-server stopped."
