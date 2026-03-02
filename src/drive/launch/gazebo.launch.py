# import os
# from launch import LaunchDescription
# from launch.actions import ExecuteProcess, TimerAction, SetEnvironmentVariable
# from launch_ros.actions import Node
# from ament_index_python.packages import get_package_share_directory

# def generate_launch_description():
#     pkg_name = 'drive'
#     kg_rover_share = get_package_share_directory(pkg_name)

#     # 1. DEFINE GAZEBO URDF FILE PATH
#     # NOTE: This file (drive_gazebo.urdf) MUST contain absolute file:// paths
#     gazebo_urdf_file_path = os.path.join(kg_rover_share, 'urdf', 'drive_gazebo.urdf')

#     # 2. SET VIRTUALIZATION GRAPHICS WORKAROUNDS (Crucial for VM stability)
#     set_gl_software = SetEnvironmentVariable(
#         name='LIBGL_ALWAYS_SOFTWARE',
#         value='1' 
#     )

#     # 3. START IGNITION GAZEBO (FORTRESS)
#     ignition = ExecuteProcess(
#         cmd=['ign', 'gazebo', '-r', '-v', '4', 'empty.sdf'],
#         output='screen',
#         additional_env={'OGRE_RTT_MODE': 'Copy'}
#     )
    
#     # 4. SPAWN THE ENTITY 
#     # Uses the file:// URDF content for guaranteed spawning.
#     spawn_entity = Node(
#         package='ros_gz_sim',
#         executable='create',
#         output='screen',
#         arguments=[
#             '-file', gazebo_urdf_file_path,  # Uses the file with file:// paths
#             '-name', 'my_robot',
#             '-x', '0.0', '-y', '0.0', '-z', '0.5'
#         ],
#     )

#     # Delay the spawn by 5 seconds to ensure the Gazebo server is ready
#     delayed_spawn = TimerAction(
#         period=5.0,
#         actions=[spawn_entity]
#     )

#     # 5. ROBOT STATE PUBLISHER (Still useful for bridge/TF even if RViz isn't open)
#     # Since you only requested Gazebo, this can be omitted, but it's often essential 
#     # for plugins or bridge communication. We will keep it but comment out the content read 
#     # as it's not strictly necessary for spawning a model via '-file'. 
#     # If you need this running for other ROS nodes, uncomment and load the original URDF.
#     # --------------------------------------------------------------------------
#     # try:
#     #     with open(os.path.join(drive_share, 'urdf', 'drive.urdf'), 'r') as infp:
#     #         robot_description_content_rviz = infp.read()
#     # except EnvironmentError:
#     #     robot_description_content_rviz = ""
#     #
#     # robot_state_publisher_node = Node(
#     #     package='robot_state_publisher',
#     #     executable='robot_state_publisher',
#     #     name='robot_state_publisher',
#     #     output='screen',
#     #     parameters=[{'robot_description': robot_description_content_rviz}],
#     # )
#     # --------------------------------------------------------------------------

#     return LaunchDescription([
#         # Graphics fix
#         set_gl_software, 
        
#         # Core Nodes
#         # robot_state_publisher_node, # Commented out as it's not strictly required for Gazebo-only view

#         # Simulation
#         ignition,
#         delayed_spawn,
#     ])







#!/usr/bin/env python3
"""
gazebo.launch.py — Launches Ignition Gazebo + rover with ros2_control
"""

import os
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    RegisterEventHandler,
    TimerAction,
)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    pkg_drive = get_package_share_directory('drive')

    # ------------------------------------------------------------------ #
    # Launch arguments
    # ------------------------------------------------------------------ #
    declare_world_arg = DeclareLaunchArgument(
        'world',
        default_value='empty.sdf',
        description='Ignition Gazebo world file name'
    )

    declare_verbose_arg = DeclareLaunchArgument(
        'verbose',
        default_value='false',
        description='Enable verbose Ignition output'
    )

    # ------------------------------------------------------------------ #
    # Robot description — read URDF file directly as a plain string.
    # Using Command([xacro, ...]) causes a yaml-parse error when the
    # substitution result is passed as a Node parameter on Humble.
    # Reading the file eagerly at launch-description-generation time
    # gives robot_state_publisher a clean string it can accept.
    # ------------------------------------------------------------------ #
    urdf_path = os.path.join(pkg_drive, 'urdf', 'drive_gazebo.urdf')
    with open(urdf_path, 'r') as f:
        robot_description_content = f.read()

    robot_description = {'robot_description': robot_description_content}

    # ------------------------------------------------------------------ #
    # robot_state_publisher — publishes TF from URDF joints
    # ------------------------------------------------------------------ #
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[robot_description],
    )

    # ------------------------------------------------------------------ #
    # Ignition Gazebo
    # ------------------------------------------------------------------ #
    ignition_gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('ros_gz_sim'),
                'launch',
                'gz_sim.launch.py'
            ])
        ]),
        launch_arguments={
            'gz_args': ['-r -v4 ', LaunchConfiguration('world')],
        }.items(),
    )

    # ------------------------------------------------------------------ #
    # Spawn robot into Gazebo (reads /robot_description topic)
    # ------------------------------------------------------------------ #
    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        name='spawn_drive',
        arguments=[
            '-name', 'drive',
            '-topic', 'robot_description',
            '-x', '0', '-y', '0', '-z', '0.3',
        ],
        output='screen',
    )

    # ------------------------------------------------------------------ #
    # ros_gz bridge — /clock (required for ros2_control sim timing)
    # ------------------------------------------------------------------ #
    gz_ros2_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='gz_ros2_bridge',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock',
            '/scan@sensor_msgs/msg/LaserScan[ignition.msgs.LaserScan',
            '/imu@sensor_msgs/msg/Imu[ignition.msgs.IMU',


        ],
        output='screen',
    )

    # ------------------------------------------------------------------ #
    # Controller spawners
    # controller_manager is started automatically by the ign_ros2_control
    # plugin that lives inside the URDF <gazebo> block.
    # ------------------------------------------------------------------ #
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        name='joint_state_broadcaster_spawner',
        arguments=[
            'joint_state_broadcaster',
            '--controller-manager', '/controller_manager',
        ],
        output='screen',
    )

    diff_drive_spawner = Node(
        package='controller_manager',
        executable='spawner',
        name='diff_drive_spawner',
        arguments=[
            'diff_drive_controller',
            '--controller-manager', '/controller_manager',

        ],
        remappings=[
            ('/diff_drive_controller/cmd_vel_unstamped', '/diff_drive_controller/cmd_vel'),
            ('/diff_drive_controller/odom', '/diff_drive_controller/odom'),
            
        ],
        output='screen',
    )

    # ------------------------------------------------------------------ #
    # Wait for spawn to finish, then activate both controllers
    # ------------------------------------------------------------------ #
    spawn_controllers = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=spawn_entity,
            on_exit=[
                TimerAction(
                    period=3.0,
                    actions=[
                        joint_state_broadcaster_spawner,
                        diff_drive_spawner,
                    ]
                )
            ]
        )
    )

    ekf_node = Node(
    package='robot_localization',
    executable='ekf_node',
    name='ekf_filter_node',
    output='screen',
    parameters=[
        os.path.join(pkg_drive, 'config', 'ekf_params.yaml'),
        {'use_sim_time': True}
        ],
    )
    
    delayed_ekf = TimerAction(
    period=5.0,
    actions=[ekf_node]
    )


# _____________________slam________________________

    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            os.path.join(pkg_drive, 'config', 'slam_toolbox_params.yaml'),
            {'use_sim_time': True}
        ],
    )

    delayed_slam = TimerAction(
        period=60.0,
        actions=[slam_toolbox_node]
    )


    # ------------------------------------------------------------------ #
    # Assemble
    # ------------------------------------------------------------------ #
    return LaunchDescription([
        declare_world_arg,
        declare_verbose_arg,

        robot_state_publisher_node,
        ignition_gazebo,
        gz_ros2_bridge,
        spawn_entity,
        spawn_controllers,
        delayed_ekf,
        delayed_slam,
    ])