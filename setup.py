from setuptools import setup
import os
from glob import glob

package_name = 'llm_robot_task_planning'

setup(
    name=package_name,
    version='1.0.0',
    packages=[
        package_name,
        f'{package_name}.controllers',
        f'{package_name}.skills',
        f'{package_name}.planner',
        f'{package_name}.nodes',
    ],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name] if os.path.exists('resource/' + package_name) else []),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*.wbt')),
    ],
    install_requires=['setuptools', 'pydantic', 'pyyaml'],
    zip_safe=True,
    maintainer='student',
    maintainer_email='student@university.edu',
    description='LLM-Assisted Mobile Robot Task Planning Package',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'webots_bridge_node = llm_robot_task_planning.nodes.webots_bridge_node:main',
            'navigation_node = llm_robot_task_planning.nodes.navigation_node:main',
            'task_agent_node = llm_robot_task_planning.nodes.task_agent_node:main',
            'keyboard_twist = llm_robot_task_planning.nodes.keyboard_twist:main',
        ],
    },
)
