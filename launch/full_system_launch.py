import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg_dir = get_package_share_directory('llm_robot_task_planning')

    llm_provider_arg = DeclareLaunchArgument(
        'llm_provider',
        default_value='qwen',
        description='LLM brain: qwen | ollama | mock (used in the printed agent command)'
    )

    robot_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_dir, 'launch', 'robot_launch.py'))
    )

    # Agent needs a keyboard terminal; print the ros2 run command for T2
    guidance = LogInfo(msg=[
        '\n' + '='*64,
        '\n Robot side started: Webots + bridge + navigation.',
        '\n Open a SECOND terminal and run the interactive brain:',
        '\n   LLM_PROVIDER=', LaunchConfiguration('llm_provider'),
        ' ros2 run llm_robot_task_planning task_agent_node',
        '\n (pick qwen / ollama / mock in that command)',
        '\n' + '='*64,
    ])

    return LaunchDescription([
        llm_provider_arg,
        robot_launch,
        guidance,
    ])
