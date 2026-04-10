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
    # 맵 파일 경로 설정
    map_file = os.path.join(pkg_dir, 'maps', 'my_store_map_02.yaml')

    # Launch arguments
    map_frame = LaunchConfiguration('map_frame', default='map')
    run_rfid = LaunchConfiguration('run_rfid', default='false')
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    use_ai_sim = LaunchConfiguration('use_ai_sim', default='false')
    use_rviz = LaunchConfiguration('use_rviz', default='true')

    bt_xml_file = os.path.join(pkg_dir, 'config', 'navigate_to_pose_w_replanning_and_recovery.xml')

    # 1. 파라미터 로드 및 치환 (추가 안전장치)
    with open(nav2_params_file, 'r') as f:
        params_data = yaml.safe_load(f)

    def deep_replace(obj, target, replacement):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if v == target:
                    obj[k] = replacement
                else:
                    deep_replace(v, target, replacement)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                if v == target:
                    obj[i] = replacement
                else:
                    deep_replace(v, target, replacement)

    deep_replace(params_data, "replace_at_runtime", bt_xml_file)

    temp_params = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml.dump(params_data, temp_params)
    modified_params_path = temp_params.name
    temp_params.close()

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
        DeclareLaunchArgument('use_rviz', default_value='true', description='Whether to run RViz'),

        # 1. Navigation2 Bringup
        GroupAction(
            actions=[
                SetRemap(src='/cmd_vel', dst='/cmd_vel_nav'),
                SetRemap(src='cmd_vel', dst='/cmd_vel_nav'),
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(nav2_bringup_dir, 'launch', 'bringup_launch.py')),
                    launch_arguments={
                        'map': map_file,
                        'use_sim_time': use_sim_time,
                        'params_file': configured_params,
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

        # 3. Patrol Main Node
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

        # 4. Obstacle Avoidance Node
        Node(
            package='patrol_main',
            executable='obstacle_node',
            name='obstacle_node',
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen'
        ),

        # 5. Twist Mux
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

        # 7. RViz2
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', os.path.join(get_package_share_directory('nav2_bringup'), 'rviz', 'nav2_default_view.rviz')],
            parameters=[{'use_sim_time': use_sim_time}],
            condition=IfCondition(use_rviz),
            output='screen'
        ),

        # 8. RFID Localization Node
        Node(
            package='patrol_main',
            executable='rfid_localization_node',
            name='rfid_localization_node',
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen',
            condition=IfCondition(run_rfid)
        ),

        # 9. AI Product Detection & Verification System (Unified)
        Node(
            package='protect_product',
            executable='integrated_node',
            name='integrated_pc_node',
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen'
        ),

        # 10. IPCAM to ROS Bridge Node (RTSP Bridge)
        Node(
            package='protect_product',
            executable='camera_node',
            name='rtsp_bridge_node',
            output='screen'
        )
    ])
