import os
import yaml
import tempfile
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node, SetRemap
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, GroupAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from nav2_common.launch import RewrittenYaml

def generate_launch_description():
    pkg_dir = get_package_share_directory('patrol_main')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')

    # Configuration file paths
    twist_mux_config = os.path.join(pkg_dir, 'config', 'twist_mux.yaml')
    nav2_params_file = os.path.join(pkg_dir, 'config', 'nav2_params.yaml')
    map_file = os.path.join(pkg_dir, 'maps', 'my_store_map_01.yaml')

    # Launch arguments
    map_frame = LaunchConfiguration('map_frame', default='map')
    run_rfid = LaunchConfiguration('run_rfid', default='false')
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    use_ai_sim = LaunchConfiguration('use_ai_sim', default='false')

    # 1. Behavior Tree XML 경로 강제 보정 (Python 기반 하드 치환)
    # [중요] RewrittenYaml이 런타임에 XML 경로(문자열)를 제대로 찾지 못하는 문제를 해결하기 위해
    # 런치 실행 시점에 파일을 직접 읽어 문자열 검색/교체를 수행합니다.
    bt_xml_file = os.path.join(pkg_dir, 'config', 'navigate_to_pose_w_replanning_and_recovery.xml')
    
    with open(nav2_params_file, 'r') as f:
        params_data = yaml.safe_load(f)
    
    # bt_navigator 섹션 강제 업데이트
    if 'bt_navigator' in params_data:
        ros_params = params_data['bt_navigator'].get('ros__parameters', {})
        if ros_params:
            ros_params['default_nav_to_pose_bt_xml'] = bt_xml_file
            ros_params['default_nav_through_poses_bt_xml'] = bt_xml_file
            params_data['bt_navigator']['ros__parameters'] = ros_params

    # 수정한 파라미터를 임시 파일에 저장 (이 파일은 로봇 프로세스가 가동되는 동안 유지됨)
    temp_params = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml.dump(params_data, temp_params)
    modified_params_path = temp_params.name
    temp_params.close()

    # 2. 파라미터 재작성 (런타임 LaunchConfiguration 대응)
    # use_sim_time 같은 실행 인자들을 다시 한 번 입힙니다.
    param_substitutions = {
        'use_sim_time': use_sim_time
    }

    configured_params = RewrittenYaml(
        source_file=modified_params_path,
        root_key='',
        param_rewrites=param_substitutions,
        convert_types=True
    )


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
                        'params_file': configured_params, # [수정] 재작성된(Rewritten) YAML 사용
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

        # 4. Obstacle Avoidance Node (LOGIC_02 패키지 사용x -> patrol_main 패키지로 통합)
        Node(
            package='patrol_main',
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
            remappings=[('cmd_vel_out', 'cmd_vel')]
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

