#!/bin/bash
# Gilbot HMI Launch Script (X11 Kiosk - Stable Version)
# Optimized for Raspberry Pi 4 CPU Rendering

# 1. 서버 정보 설정 (필요 시 여기를 수정)
SERVER_IP="192.168.0.7"
SERVER_PORT="8000"

# Clean up any existing instances
sudo killall Xorg X chromium-browser matchbox-window-manager -q
sudo rm -f /tmp/.X0-lock /tmp/.X11-unix/X0

# Launch X Server + Window Manager + Chromium
# --disable-gpu: Mandatory for stable Pi 4 headless X11
# --no-sandbox: Required for Snap-based Chromium in some headless configs
# --disable-dev-shm-usage: Prevents crashes in low-memory/container scenarios
xinit /bin/sh -c "matchbox-window-manager -use_titlebar no & chromium-browser --kiosk --window-size=800,480 --window-position=0,0 --no-sandbox --disable-gpu --disable-software-rasterizer --disable-dev-shm-usage --disable-features=Translate,PasswordImport,AutofillAddressEnabled,TouchpadAndWheelScrollLatching --ozone-platform=x11 http://$SERVER_IP:$SERVER_PORT/hmi/index.html" -- :0 -nolisten tcp vt7
