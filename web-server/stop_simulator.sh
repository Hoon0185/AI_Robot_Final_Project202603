#!/bin/bash

# Gilbot Simulator Force Stop Script
# This script finds and kills any running simulate_robot.py processes.

echo "Finding robot simulator processes..."
PIDS=$(pgrep -f simulate_robot.py)

if [ -z "$PIDS" ]; then
    echo "No running simulator found."
else
    echo "Stopping simulator (PIDs: $PIDS)..."
    pkill -9 -f simulate_robot.py
    echo "Simulator stopped successfully."
fi
