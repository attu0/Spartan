from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

# name, default, python type
ARGS = [
    ("device", "-1", int),                       # -1 = auto-detect "CCB Camera"
    ("scale", "0.25", float),
    ("num_disp", "32", int),
    ("stride", "1", int),
    ("max_rate", "10.0", float),
    ("z_min", "0.3", float),
    ("z_max", "5.0", float),
    ("frame_id", "stereo_optical_frame", str),
    ("calib", "", str),                          # empty = packaged config/stereo_calib.npz
]


def generate_launch_description():
    decls = [DeclareLaunchArgument(n, default_value=v) for n, v, _ in ARGS]
    decls.append(DeclareLaunchArgument(
        "static_tf", default_value="true",
        description="publish map -> stereo_optical_frame (turn off once the rover has a real TF tree)"))

    params = {n: ParameterValue(LaunchConfiguration(n), value_type=t) for n, _, t in ARGS}

    stereo = Node(package="spartan_depth_cam", executable="stereo_node",
                  name="stereo_node", output="screen", parameters=[params])

    tf = Node(package="tf2_ros", executable="static_transform_publisher",
              arguments=["--frame-id", "map", "--child-frame-id", LaunchConfiguration("frame_id"),
                         "--roll", "-1.5708", "--pitch", "0", "--yaw", "-1.5708"],
              condition=IfCondition(LaunchConfiguration("static_tf")))

    return LaunchDescription(decls + [stereo, tf])
