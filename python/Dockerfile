# ROS 2 Jazzy container for the Spartan stereo depth camera (Arduino UNO Q, arm64).
# Build context is this folder (python/): src/ holds the ROS 2 packages.
FROM ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-opencv \
        python3-numpy \
        python3-setuptools \
        python3-colcon-common-extensions \
        ros-jazzy-tf2-ros \
        v4l-utils \
        tmux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ws
COPY src/ /ws/src/
RUN . /opt/ros/jazzy/setup.sh && colcon build

# every shell (docker exec -it ... bash / tmux panes) gets ROS + the workspace
RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc \
 && echo "source /ws/install/setup.bash" >> /root/.bashrc

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
