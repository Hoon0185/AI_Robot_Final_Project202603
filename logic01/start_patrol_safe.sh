#!/bin/bash
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch patrol_main total_patrol.launch.py run_obstacle_node:=false
