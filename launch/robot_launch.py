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

    # Webots robot bridge (drives /agent0, publishes GPS/IMU)
    bridge_node = Node(
        package='llm_robot_task_planning',
        executable='webots_bridge_node',
        name='webots_bridge_node',
        output='screen'
    )

    # Closed-loop navigation controller
    navigation_node = Node(
        package='llm_robot_task_planning',
        executable='navigation_node',
        name='navigation_node',
        output='screen'
    )

    # task_agent_node is not started here: 'ros2 launch' does not forward
    # keyboard input. Start it in a second terminal with ros2 run.

    return LaunchDescription([
        webots,
        bridge_node,
        navigation_node,
    ])
