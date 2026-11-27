#!/bin/bash
set -e

source /opt/ros/jazzy/setup.bash
if [ -f /opt/ros_ws/install/setup.bash ]; then
  source /opt/ros_ws/install/setup.bash
fi

exec "$@"