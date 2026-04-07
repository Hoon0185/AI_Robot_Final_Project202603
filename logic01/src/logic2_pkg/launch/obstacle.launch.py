import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # 패키지 공유 디렉토리 경로 획득
    logic2_pkg_share = get_package_share_directory('logic2_pkg')

    # twist_mux 설정 파일 경로 (절대 경로)
    twist_mux_config = os.path.join(logic2_pkg_share, 'config', 'twist_mux.yaml')

    # Obstacle node (장애물 감지 및 우회 제어)
    obstacle_node = Node(
        package='logic2_pkg',
        executable='obstacle_node',
        name='obstacle_node',
        parameters=[{'use_sim_time': True}],
        output='screen'
    )

    # Twist Mux node (명령어 우선순위 관리)
    twist_mux_node = Node(
        package='twist_mux',
        executable='twist_mux',
        name='twist_mux',
        parameters=[
            twist_mux_config,
            {'use_sim_time': True}
        ],
        remappings=[('cmd_vel_out', 'cmd_vel')],
        output='screen'
    )

    return LaunchDescription([
        obstacle_node,
        twist_mux_node
    ])
