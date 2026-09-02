#!/usr/bin/env bash
# ==============================================================================
# Environment Setup Script for LLM-Assisted Mobile Robot Task Planning
# Target OS: Ubuntu 22.04 LTS (Jammy Jellyfish)
# Middleware: ROS 2 Humble Hawksbill
# Simulator: Webots R2025a
# ==============================================================================

set -e

echo "======================================================================"
echo " 1. Updating System Packages and Installing Core Build Dependencies"
echo "======================================================================"
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl gnupg2 lsb-release software-properties-common git \
                    python3-pip python3-setuptools python3-colcon-common-extensions \
                    python3-rosdep python3-vcstool wget

echo "======================================================================"
echo " 2. Setting up ROS 2 Humble Repositories & Installing ROS 2 Base"
echo "======================================================================"
sudo add-apt-repository universe -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(source /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install -y ros-humble-desktop ros-humble-ros-base ros-humble-teleop-twist-keyboard

# Initialize rosdep
if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
    sudo rosdep init || true
fi
rosdep update

echo "======================================================================"
echo " 3. Installing Webots R2025a & webots_ros2 interface"
echo "======================================================================"
sudo mkdir -p /etc/apt/keyrings
cd /etc/apt/keyrings
sudo wget -q https://cyberbotics.com/Cyberbotics.asc
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/Cyberbotics.asc] https://cyberbotics.com/debian binary-amd64/" | sudo tee /etc/apt/sources.list.d/Cyberbotics.list
sudo apt update
sudo apt install -y webots ros-humble-webots-ros2

# Set WEBOTS_HOME
export WEBOTS_HOME=/usr/local/webots
echo "export WEBOTS_HOME=/usr/local/webots" >> ~/.bashrc
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc

echo "======================================================================"
echo " 4. Installing Python AI & Testing Dependencies"
echo "======================================================================"
pip3 install --upgrade pip
pip3 install pydantic pyyaml pytest openai

echo "======================================================================"
echo " 5. Building ROS 2 Workspace"
echo "======================================================================"
mkdir -p ~/ros2_ws/src
cp -r $(pwd) ~/ros2_ws/src/llm_robot_task_planning || true

cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install

echo "source ~/ros2_ws/install/setup.bash" >> ~/.bashrc

echo "======================================================================"
echo " [SUCCESS] Environment Setup Complete!"
echo " Please reload your shell with: source ~/.bashrc"
echo " You can now launch the system with:"
echo "   ros2 launch llm_robot_task_planning robot_launch.py"
echo "======================================================================"
