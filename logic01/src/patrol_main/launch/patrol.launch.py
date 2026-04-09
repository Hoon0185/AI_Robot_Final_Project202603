import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node, PushRosNamespace
from launch.actions import GroupAction, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition

def generate_launch_description():
    pkg_dir = get_package_share_directory('patrol_main')

    # 1. 런치 인자 선언
    namespace_arg = DeclareLaunchArgument(
        'namespace',
        default_value='',
        description='Robot namespace'
    )
    map_frame_arg = DeclareLaunchArgument(
        'map_frame',
        default_value='map',
        description='Map frame name'
    )
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation (Gazebo) clock if true'
    )
    run_rfid_arg = DeclareLaunchArgument(
        'run_rfid',
        default_value='false',
        description='Whether to run RFID localization node'
    )

    namespace_config = LaunchConfiguration('namespace')
    map_frame = LaunchConfiguration('map_frame')
    use_sim_time = LaunchConfiguration('use_sim_time')
    run_rfid = LaunchConfiguration('run_rfid')

    # 2. 설정 파일 경로
    shelf_config = os.path.join(pkg_dir, 'config', 'shelf_coords.yaml')

    # Behavior Tree XML 파일의 동적 절대 경로 완성
    bt_xml_file = os.path.join(pkg_dir, 'config', 'navigate_to_pose_w_replanning_and_recovery.xml')

    # 3. 모든 순찰 관련 노드 실행 (네임스페이스 제거됨)
    patrol_actions = [

            # (1) 순찰 스케줄러 (주기적/예약 실행 관리)
            Node(
                package='patrol_main',
                executable='patrol_scheduler',
                name='patrol_scheduler',
                parameters=[shelf_config, {'use_sim_time': use_sim_time}],
                output='screen'
            ),

            # (2) 순찰 메인 노드 (Nav2 목표 전송 및 상태 관리)
            Node(
                package='patrol_main',
                executable='patrol_node',
                name='patrol_node',
                parameters=[shelf_config, {
                    'use_sim_time': use_sim_time,
                    'map_frame': map_frame,
                    'default_nav_to_pose_bt_xml': bt_xml_file
                }],
                output='screen'
            ),

            # (5) 순찰 시각화 (RVIZ Marker 관리)
            Node(
                package='patrol_main',
                executable='patrol_visualizer',
                name='patrol_visualizer',
                parameters=[{'use_sim_time': use_sim_time, 'map_frame': map_frame}],
                output='screen'
            ),

            # (6) 장애물 회피 및 관리 노드 (추가됨)
            Node(
                package='patrol_main',
                executable='obstacle_node',
                name='obstacle_node',
                parameters=[{'use_sim_time': use_sim_time}],
                output='screen'
            ),

            # (7) RFID 로컬라이제이션 보정 노드 (선택 사항)
            Node(
                package='patrol_main',
                executable='rfid_localization_node',
                name='rfid_localization_node',
                parameters=[{'use_sim_time': use_sim_time}],
                output='screen',
                condition=IfCondition(run_rfid)
            )
    ]

    return LaunchDescription([
        namespace_arg,
        map_frame_arg,
        use_sim_time_arg,
        run_rfid_arg,
        *patrol_actions
    ])
