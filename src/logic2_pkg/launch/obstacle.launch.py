import os
from launch import LaunchDescription
from launch_ros.actions import Node, PushRosNamespace
from launch.actions import GroupAction

def generate_launch_description():
  # TB3_2 네임스페이스로 그룹화
  obstacle_group = GroupAction(
    actions=[
      PushRosNamespace('TB3_2'), # 팀원과 동일한 네임스페이스 적용

      Node( # Obstacle Manager 노드
        package='logic2_pkg',
        executable='obstacle_manager',
        name='obstacle_manager',
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
        remappings=[('cmd_vel_out', 'cmd_vel')], # 최종 출력을 /TB3_2/cmd_vel로 보냄
        output='screen'
      ),
    ]
  )

  return LaunchDescription([obstacle_group])
