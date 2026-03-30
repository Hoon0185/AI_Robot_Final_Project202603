import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    # 패키지 경로 설정
    patrol_pkg_dir = get_package_share_directory('patrol_main')
    logic2_pkg_dir = get_package_share_directory('logic2_pkg')

    # 'namespace' 런처 인자 선언
    namespace_arg = DeclareLaunchArgument(
        'namespace',
        default_value='',
        description='Robot namespace'
    )
    namespace_config = LaunchConfiguration('namespace')

    # 1. Patrol Launch 포함 (순찰 로직)
    patrol_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(patrol_pkg_dir, 'launch', 'patrol.launch.py')
        ),
        launch_arguments={'namespace': namespace_config}.items()
    )

    # 2. Obstacle & Twist Mux Launch 포함 (장애물 및 우선순위 제어)
    obstacle_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(logic2_pkg_dir, 'launch', 'obstacle.launch.py')
        ),
        launch_arguments={'namespace': namespace_config}.items()
    )

    return LaunchDescription([
        namespace_arg,
        obstacle_launch,
        patrol_launch
    ])
