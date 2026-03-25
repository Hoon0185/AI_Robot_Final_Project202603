import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    pkg_dir = get_package_share_directory('patrol_main')
    
    # 설정 파일 경로
    config_file = os.path.join(pkg_dir, 'config', 'shelf_coords.yaml')
    
    return LaunchDescription([
        Node(
            package='patrol_main',
            executable='patrol_scheduler',
            name='patrol_scheduler',
            parameters=[config_file],
            output='screen'
        ),
        Node(
            package='patrol_main',
            executable='patrol_node',
            name='patrol_node',
            parameters=[config_file],
            output='screen'
        ),
        Node(
            package='patrol_main',
            executable='patrol_visualizer',
            name='patrol_visualizer',
            parameters=[config_file],
            output='screen'
        )
    ])
