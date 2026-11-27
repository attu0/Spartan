import os
from glob import glob

from setuptools import find_packages, setup

package_name = "spartan_depth_cam"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.py")),
        (os.path.join("share", package_name, "config"), glob("config/*")),
        (os.path.join("share", package_name, "rviz"), glob("rviz/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Atharv",
    maintainer_email="atharv@example.com",
    description="AR0144 stereo camera calibration, depth and point cloud for the Spartan rover",
    license="MIT",
    entry_points={
        "console_scripts": [
            "stereo_node = spartan_depth_cam.stereo_node:main",
            "capture_pairs = spartan_depth_cam.capture_pairs:main",
            "calibrate = spartan_depth_cam.calibrate:main",
        ],
    },
)
