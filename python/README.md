# Spartan - python workspace

`src/spartan_depth_cam` - ROS 2 (Jazzy, ament_python) package for the AR0144 stereo camera:
`stereo_node` (rectified images, camera_info, depth colormap, PointCloud2), `capture_pairs` and
`calibrate` (calibration tools), `launch/stereo.launch.py`, `config/stereo_calib.npz`.

Build/run natively:   colcon build --packages-select spartan_depth_cam && ros2 launch spartan_depth_cam stereo.launch.py
Build/run in Docker:  docker compose build && docker compose up   (this folder)
