import os
from launch import LaunchDescription
from launch_ros.actions import Node, PushRosNamespace
from launch.actions import GroupAction, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
  # 'namespace' 런처 인자 선언 (기본값은 빈 문자열)
  namespace_arg = DeclareLaunchArgument(
    'namespace',
    default_value='',
    description='Robot namespace'
  )
  namespace_config = LaunchConfiguration('namespace')

  obstacle_group = GroupAction(
    actions=[
      PushRosNamespace(namespace_config),

      Node( # Obstacle node 노드
        package='logic2_pkg',
        executable='obstacle_node',
        name='obstacle_node',
        parameters=[{'use_sim_time': True}],
        output='screen'
      ),
      Node( # Twist Mux 노드 (교통 정리)
        package='twist_mux',
        executable='twist_mux',
        name='twist_mux',
        parameters=[{
          'use_sim_time': True,
          'twist_mux_config': os.path.join(
            'config',
            'twist_mux.yaml'
          )
        }],
        remappings=[('cmd_vel_out', 'cmd_vel')],
        output='screen'
      ),
    ]
  )

  return LaunchDescription([
    namespace_arg,
    obstacle_group
  ])
