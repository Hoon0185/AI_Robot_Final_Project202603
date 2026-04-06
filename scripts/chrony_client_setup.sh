#!/bin/bash

# Gilbot Chrony Client Setup Script (Environment-Aware)
# This script configures the robot to sync its time with the specified Master.

WORKSTATION_IP="192.168.1.3"
LIGHTSAIL_IP="16.184.56.119"

# Default to Local unless specified
MASTER_IP=$WORKSTATION_IP
MODE="LOCAL (Workstation)"

# Argument handling
if [[ "$1" == "--remote" ]]; then
    MASTER_IP=$LIGHTSAIL_IP
    MODE="REMOTE (Lightsail)"
elif [[ "$1" == "--local" ]]; then
    MASTER_IP=$WORKSTATION_IP
    MODE="LOCAL (Workstation)"
elif [[ -n "$1" ]]; then
    MASTER_IP="$1"
    MODE="CUSTOM ($1)"
fi

echo "===================================================="
echo "  🚀 Gilbot Chrony Client Setup [Mode: $MODE]"
echo "  🎯 Target Master: $MASTER_IP"
echo "===================================================="

echo "[1/5] Checking for Chrony installation..."
if ! command -v chronyd &> /dev/null; then
    echo "Installing Chrony..."
    sudo apt update && sudo apt install chrony -y
fi

echo "[2/5] Configuring Chrony to sync with Master ($MASTER_IP)..."
# Backup existing config
sudo cp /etc/chrony/chrony.conf /etc/chrony/chrony.conf.bak 2>/dev/null

# Create new config
# Note: Using 'server' instead of 'pool' for direct master connection
sudo bash -c "cat <<EOF > /etc/chrony/chrony.conf
# Chrony client config for Gilbot [$MODE]
server $MASTER_IP iburst
keyfile /etc/chrony/chrony.keys
driftfile /var/lib/chrony/chrony.drift
logdir /var/log/chrony
maxupdateskew 100.0
rtcsync
makestep 1 3
EOF"

echo "[3/5] Restarting Chrony service..."
sudo systemctl restart chrony
sudo systemctl enable chrony

echo "[4/5] Disabling systemd-timesyncd to avoid conflicts..."
sudo systemctl stop systemd-timesyncd 2>/dev/null
sudo systemctl disable systemd-timesyncd 2>/dev/null

echo "[5/5] Waiting for synchronization status..."
sleep 3
chronyc tracking
echo ""
chronyc sources -v

echo "===================================================="
echo "  ✅ Chrony Client Setup Complete! ($MODE)"
echo "===================================================="
