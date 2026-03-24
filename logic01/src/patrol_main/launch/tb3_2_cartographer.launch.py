from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, GroupAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import PushRosNamespace
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    # 1. 경로 설정
    pkg_share = get_package_share_directory('patrol_main')
    cartographer_config_dir = os.path.join(pkg_share, 'config')
    configuration_basename = 'tb3_2_lds_2d.lua'

    # 2. TB3_2 네임스페이스와 함께 노드 실행 (직접 Node 선언하여 확실하게 리매핑)
    from launch_ros.actions import Node
    
    cartographer_node = Node(
        package='cartographer_ros',
        executable='cartographer_node',
        name='cartographer_node',
        namespace='TB3_2',
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'map_frame': 'TB3_2/map',
            'tracking_frame': 'TB3_2/base_footprint',
            'published_frame': 'TB3_2/odom',
            'odom_frame': 'TB3_2/odom'
        }],
        arguments=['-configuration_directory', cartographer_config_dir,
                   '-configuration_basename', configuration_basename],
        remappings=[
            ('scan', 'scan'), # Namespace가 이미 TB3_2이므로 scan은 /TB3_2/scan이 됨
            ('odom', 'odom'),
            ('imu', 'imu')
        ]
    )

    # 3.Occupancy Grid 노드 추가 (맵 데이터 생성용)
    occupancy_grid_node = Node(
        package='cartographer_ros',
        executable='cartographer_occupancy_grid_node',
        name='cartographer_occupancy_grid_node',
        namespace='TB3_2',
        output='screen',
        parameters=[{'use_sim_time': True}],
        arguments=['-resolution', '0.05', '-publish_period_sec', '1.0']
    )

    # 4. RViz2 노드 추가 (시각화용)
    rviz_config_dir = os.path.join(get_package_share_directory('turtlebot3_cartographer'),
                                   'rviz', 'tb3_cartographer.rviz')
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        namespace='TB3_2',
        arguments=['-d', rviz_config_dir],
        parameters=[{'use_sim_time': True}],
        output='screen'
    )

    return LaunchDescription([
        cartographer_node,
        occupancy_grid_node,
        rviz_node
    ])
