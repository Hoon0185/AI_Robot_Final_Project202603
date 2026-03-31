import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    pkg_dir = get_package_share_directory('patrol_main')
    
    # Configuration file paths
    twist_mux_config = os.path.join(pkg_dir, 'config', 'twist_mux.yaml')
    
    # Launch arguments
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    map_frame = LaunchConfiguration('map_frame', default='map')

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('map_frame', default_value='map'),

        # 1. Patrol Scheduler Node
        Node(
            package='patrol_main',
            executable='patrol_scheduler',
            name='patrol_scheduler',
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen'
        ),

        # 2. Patrol Main Node (Navigation Goal Sender)
        Node(
            package='patrol_main',
            executable='patrol_node',
            name='patrol_node',
            parameters=[{
                'use_sim_time': use_sim_time,
                'map_frame': map_frame
            }],
            output='screen'
        ),

        # 3. Obstacle Avoidance Node (LOGIC_02 Integration)
        Node(
            package='patrol_main',
            executable='obstacle_node',
            name='patrol_obstacle_node',
            parameters=[{
                'use_sim_time': use_sim_time,
                'obstacle_wait_time': 10
            }],
            output='screen'
        ),

        # 4. Twist Mux (Priority Management)
        Node(
            package='twist_mux',
            executable='twist_mux',
            name='twist_mux',
            output='screen',
            parameters=[twist_mux_config, {'use_sim_time': use_sim_time}],
            remappings=[('/cmd_vel_out', '/cmd_vel')] # 최종 출력 토픽
        ),

        # 5. Patrol Visualizer (Optional but helpful)
        Node(
            package='patrol_main',
            executable='patrol_visualizer',
            name='patrol_visualizer',
            parameters=[{'use_sim_time': use_sim_time, 'map_frame': map_frame}],
            output='screen'
        )
    ])
