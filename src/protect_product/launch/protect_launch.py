import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # 패키지 이름 변수로 설정
    package_name = 'protect_product'

    # 1. Detector 노드 설정 (YOLO 추론)
    detector_node = Node(
        package=package_name,
        executable='detector',
        name='detector_node',
        output='screen',
        emulate_tty=True,
        parameters=[{'use_sim_time': False}] # 실물 로봇 = False
    )

    # 2. Verifier 노드 설정 (QR 인식 및 DB 대조)
    verifier_node = Node(
        package=package_name,
        executable='verifier',
        name='verifier_node',
        output='screen',
        emulate_tty=True
    )

    # 3. Viewer 노드 설정 (최종 GUI 출력)
    viewer_node = Node(
        package=package_name,
        executable='viewer',
        name='viewer_node',
        output='screen',
        emulate_tty=True
    )

    # 실행할 노드 리스트 반환
    return LaunchDescription([
        detector_node,
        verifier_node,
        viewer_node
    ])
