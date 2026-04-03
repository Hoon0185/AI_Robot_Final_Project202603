import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node, PushRosNamespace
from launch.actions import GroupAction, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    pkg_dir = get_package_share_directory('patrol_main')

    # 'namespace' 런처 인자 선언 (기본값은 빈 문자열로, 네임스페이스 없이 실행)
    namespace_arg = DeclareLaunchArgument(
        'namespace',
        default_value='',
        description='Robot namespace'
    )
    namespace_config = LaunchConfiguration('namespace')

    # 설정 파일 경로
    config_file = os.path.join(pkg_dir, 'config', 'shelf_coords.yaml')

    # 모든 노드를 지정된 네임스페이스로 그룹화
    patrol_group = GroupAction(
        actions=[
            PushRosNamespace(namespace_config),
            # 1. 순찰 스케줄러 노드
            Node(
                package='patrol_main',
                executable='patrol_scheduler',
                name='patrol_scheduler',
                parameters=[config_file],
                output='screen'
            ),
            # 2. 순찰 메인 노드 (주행 명령 및 DB 로드)
            Node(
                package='patrol_main',
                executable='patrol_node',
                name='patrol_node',
                parameters=[config_file],
                output='screen'
            ),
            # 3. 순찰 비주얼라이저 노드
            Node(
                package='patrol_main',
                executable='patrol_visualizer',
                name='patrol_visualizer',
                parameters=[config_file],
                output='screen'
            ),
        ]
    )

    return LaunchDescription([
        namespace_arg,
        patrol_group
    ])
