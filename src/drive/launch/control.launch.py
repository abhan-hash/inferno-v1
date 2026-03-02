from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from launch.substitutions import Command, PathJoinSubstitution

import os

def generate_launch_description():
    pkg_share = get_package_share_directory('drive')  # replace 'drive' with your package name
    urdf_path = os.path.join(pkg_share, 'urdf', 'drive_gazebo.urdf')  # replace filename
    ros2_control_yaml = os.path.join(pkg_share, 'config', 'ros2_control.yaml')

    # If you use xacro, replace Command([...]) accordingly to expand xacro
    robot_description = Command(['cat ', urdf_path])

    return LaunchDescription([
        Node(
            package='controller_manager',
            executable='ros2_control_node',
            parameters=[{'robot_description': robot_description}, ros2_control_yaml],
            output='screen'
        ),

        # spawn joint_state_broadcaster
        Node(
            package='controller_manager',
            executable='spawner',
            arguments=['joint_state_broadcaster'],
        ),

        # spawn diff drive controller
        Node(
            package='controller_manager',
            executable='spawner',
            arguments=['diff_drive_controller'],
        ),
    ])
