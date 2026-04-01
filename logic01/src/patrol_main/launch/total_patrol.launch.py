import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node, SetRemap
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, GroupAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    pkg_dir = get_package_share_directory('patrol_main')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')

    # Configuration file paths
    # LOGIC_02의 설정을 우선하여 사용
    twist_mux_config = os.path.join(get_package_share_directory('logic2_pkg'), 'config', 'twist_mux.yaml')
    nav2_params_file = os.path.join(pkg_dir, 'config', 'nav2_params.yaml') # 우리 패키지의 파라미터 사용
    map_file = os.path.join(pkg_dir, 'maps', 'my_store_map_01.yaml') # 실제 지도 이름으로 수정

    # Launch arguments
    map_frame = LaunchConfiguration('map_frame', default='map')
    run_rfid = LaunchConfiguration('run_rfid', default='false')
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    use_ai_sim = LaunchConfiguration('use_ai_sim', default='false')


    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('map_frame', default_value='map'),
        DeclareLaunchArgument('run_rfid', default_value='false', description='Whether to run RFID localization node'),
        DeclareLaunchArgument('use_ai_sim', default_value='false', description='Whether to use AI detection simulation'),

        # 1. Navigation2 Bringup (Forced Remap cmd_vel to cmd_vel_nav)
        # GroupAction과 SetRemap(상대+절대)을 모두 사용하여 컨테이너 내부 노드까지 강제 리매핑합니다.
        GroupAction(
            actions=[
                SetRemap(src='/cmd_vel', dst='/cmd_vel_nav'),
                SetRemap(src='cmd_vel', dst='/cmd_vel_nav'),
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(nav2_bringup_dir, 'launch', 'bringup_launch.py')),
                    launch_arguments={
                        'map': map_file,
                        'use_sim_time': use_sim_time,
                        'params_file': nav2_params_file,
                        'autostart': 'true'
                    }.items()
                ),
            ]
        ),

        # 2. Patrol Scheduler Node
        Node(
            package='patrol_main',
            executable='patrol_scheduler',
            name='patrol_scheduler',
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen'
        ),

        # 3. Patrol Main Node (Navigation Goal Sender)
        Node(
            package='patrol_main',
            executable='patrol_node',
            name='patrol_node',
            parameters=[{
                'use_sim_time': use_sim_time,
                'map_frame': map_frame,
                'use_ai_sim': use_ai_sim
            }],
            output='screen'
        ),

        # 4. Obstacle Avoidance Node (LOGIC_02 패키지 사용)
        Node(
            package='logic2_pkg',
            executable='obstacle_node',
            name='obstacle_node',
            parameters=[{
                'use_sim_time': use_sim_time
            }],
            output='screen'
        ),

        # 5. Twist Mux (Final Arbitrator)
        # Nav2 신호를 리매핑된 토픽(/cmd_vel_nav)으로 받고, 최종 명령은 /cmd_vel로 내보냅니다.
        Node(
            package='twist_mux',
            executable='twist_mux',
            name='twist_mux',
            output='screen',
            parameters=[twist_mux_config, {'use_sim_time': use_sim_time}],
            remappings=[('/cmd_vel_out', '/cmd_vel')]
        ),

        # 6. Patrol Visualizer
        Node(
            package='patrol_main',
            executable='patrol_visualizer',
            name='patrol_visualizer',
            parameters=[{'use_sim_time': use_sim_time, 'map_frame': map_frame}],
            output='screen'
        ),

        # 7. RFID Localization Node (Optional Correction)
        Node(
            package='patrol_main',
            executable='rfid_localization_node',
            name='rfid_localization_node',
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen',
            condition=IfCondition(run_rfid)
        ),

        # 8. AI Product Detection System (added from main branch)
        Node(
            package='protect_product',
            executable='detector_node',
            name='detector_node',
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen'
        ),
        Node(
            package='protect_product',
            executable='verifier_node',
            name='verifier_node',
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen'
        )
    ])

