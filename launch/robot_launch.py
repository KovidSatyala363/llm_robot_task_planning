import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from webots_ros2_driver.webots_launcher import WebotsLauncher

def generate_launch_description():
    pkg_dir = get_package_share_directory('llm_robot_task_planning')
    world_path = os.path.join(pkg_dir, 'worlds', 'lab_world.wbt')

    webots = WebotsLauncher(
        world=world_path,
        mode='realtime'
    )

    bridge_node = Node(
        package='llm_robot_task_planning',
        executable='webots_bridge_node',
        name='webots_bridge_node',
        output='screen'
    )

    return LaunchDescription([
        webots,
        bridge_node,
    ])
