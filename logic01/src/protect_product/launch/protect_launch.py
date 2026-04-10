import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    package_name = 'protect_product'

    # 1. RTSP 카메라 브릿지 실행 (영상 송출)
    camera_node = Node(
        package=package_name,
        executable='rtsp_camera',
        name='rtsp_camera_node',
        output='screen'
    )

    # 2. 통합 AI 인식 및 검증 노드 (On-demand)
    integrated_node = Node(
        package=package_name,
        executable='integrated_node',
        name='integrated_pc_node',
        output='screen',
        parameters=[{'use_sim_time': False}]
    )

    return LaunchDescription([
        camera_node,
        integrated_node
    ])
