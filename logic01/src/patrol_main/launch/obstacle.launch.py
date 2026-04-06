import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node, PushRosNamespace
from launch.actions import GroupAction, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
  pkg_dir = get_package_share_directory('patrol_main')

  # 런처 인자 선언
  namespace_arg = DeclareLaunchArgument(
    'namespace',
    default_value='',
    description='Robot namespace'
  )
  use_sim_time_arg = DeclareLaunchArgument(
    'use_sim_time',
    default_value='false',
    description='Use simulation time if true'
  )

  namespace_config = LaunchConfiguration('namespace')
  use_sim_time = LaunchConfiguration('use_sim_time')

  # twist_mux 설정 파일 경로
  twist_mux_config = os.path.join(pkg_dir, 'config', 'twist_mux.yaml')

  # 모든 노드를 지정된 네임스페이스로 그룹화
  obstacle_group = GroupAction(
    actions=[
      PushRosNamespace(namespace_config),

      Node(
          package='patrol_main',
          executable='obstacle_node',
          name='patrol_obstacle_node',
          parameters=[{
            'use_sim_time': use_sim_time,
          }],
          output='screen'
      ),
      Node(
          package='twist_mux',
          executable='twist_mux',
          name='twist_mux',
          output='screen',
          parameters=[twist_mux_config, {'use_sim_time': use_sim_time}],
          remappings=[('cmd_vel_out', 'cmd_vel')] # 최종 출력 토픽 (네임스페이스 결합 고려 슬래시 제거)
      )
    ]
  )

  return LaunchDescription([
    namespace_arg,
    use_sim_time_arg,
    obstacle_group
  ])
