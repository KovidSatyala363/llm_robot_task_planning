from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='llm_robot_task_planning',
            executable='navigation_node',
            name='navigation_node',
            output='screen'
        ),
        Node(
            package='llm_robot_task_planning',
            executable='task_agent_node',
            name='task_agent_node',
            output='screen'
        ),
    ])
