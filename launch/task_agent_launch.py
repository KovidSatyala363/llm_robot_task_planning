from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Batch/headless launcher: runs the test cases automatically (no keyboard).
    # For interactive typing use ros2 run in a separate terminal.
    llm_provider_arg = DeclareLaunchArgument(
        'llm_provider',
        default_value='',
        description='LLM brain: qwen | ollama | mock. Empty = LLM_PRIORITY / .env.'
    )

    set_provider_env = SetEnvironmentVariable(
        name='LLM_PROVIDER',
        value=LaunchConfiguration('llm_provider')
    )

    # Run the fixed test cases at startup instead of interactive mode
    set_auto_tests = SetEnvironmentVariable(
        name='LLM_AUTO_TESTS',
        value='1'
    )

    return LaunchDescription([
        llm_provider_arg,
        set_provider_env,
        set_auto_tests,
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
