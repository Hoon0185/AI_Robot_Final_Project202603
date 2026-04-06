#!/bin/bash

# Gilbot Chrony Client Setup Script
# This script configures the robot to sync its time with the workstation (Master).

MASTER_IP="192.168.1.3"

echo "Checking for Chrony installation..."
if ! command -v chronyd &> /dev/null; then
    echo "Installing Chrony..."
    sudo apt update && sudo apt install chrony -y
fi

echo "Configuring Chrony to sync with Master ($MASTER_IP)..."
# Backup existing config
sudo cp /etc/chrony/chrony.conf /etc/chrony/chrony.conf.bak

# Create new config
sudo bash -c "cat <<EOF > /etc/chrony/chrony.conf
# Chrony client config for Gilbot
server \$MASTER_IP iburst
keyfile /etc/chrony/chrony.keys
driftfile /var/lib/chrony/chrony.drift
logdir /var/log/chrony
maxupdateskew 100.0
rtcsync
makestep 1 3
EOF"

echo "Restarting Chrony service..."
sudo systemctl restart chrony
sudo systemctl enable chrony

# Disable systemd-timesyncd to avoid conflicts
sudo systemctl stop systemd-timesyncd
sudo systemctl disable systemd-timesyncd

echo "Waiting for synchronization status..."
sleep 5
chronyc tracking
chronyc sources -v

echo "Chrony Client Setup Complete!"
