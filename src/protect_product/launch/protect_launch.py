import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # 패키지 이름 변수로 설정
    package_name = 'protect_product'

    # # 1. Detector 노드 설정 (YOLO 추론)
    # detector_node = Node(
    #     package=package_name,
    #     executable='detector',
    #     name='detector_node',
    #     output='screen',
    #     emulate_tty=True,
    #     parameters=[{'use_sim_time': False}] # 실물=False, simulation(가상 시간)=True / 동기화 실패 및 TF(좌표)오류 대비
    # )

    # 1-1. Product Detector 노드 설정 (YOLO 추론 전문)
    product_detector_node = Node(
        package=package_name,
        executable='product_detector',
        name='product_detector_node',
        output='screen',
        emulate_tty=True,
        parameters=[{'use_sim_time': False}]
    )

    # 1-2. QR Detector 노드 설정 (QR 스캔 및 전처리 전문)
    qr_detector_node = Node(
        package=package_name,
        executable='qr_detector',
        name='qr_detector_node',
        output='screen',
        emulate_tty=True,
        parameters=[{'use_sim_time': False}]
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
        #detector_node,
        product_detector_node,
        qr_detector_node,
        verifier_node,
        viewer_node
    ])
