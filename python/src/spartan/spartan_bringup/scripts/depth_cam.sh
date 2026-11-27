#!/usr/bin/env bash
set -e

source /opt/ros/jazzy/setup.bash
if [ -f /opt/ros_ws/install/setup.bash ]; then
  source /opt/ros_ws/install/setup.bash
fi

# Add your depth camera launch command(s) here
ros2 launch spartan_depth_cam stereo.launch.py