import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node, PushRosNamespace
from launch.actions import GroupAction, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
  # Obstacle node 노드
  obstacle_node = Node(
    package='logic2_pkg',
    executable='obstacle_node',
    name='obstacle_node',
    parameters=[{'use_sim_time': True}],
    output='screen'
  )

  # Twist Mux 노드 (교통 정리)
  twist_mux_node = Node(
    package='twist_mux',
    executable='twist_mux',
    name='twist_mux',
    parameters=[os.path.join(
      get_package_share_directory('logic2_pkg'),
      'config',
      'twist_mux.yaml'
    ), {
      'use_sim_time': True
    }],
    remappings=[('cmd_vel_out', 'cmd_vel')],
    output='screen'
  )

  return LaunchDescription([
    obstacle_node,
    twist_mux_node
  ])
