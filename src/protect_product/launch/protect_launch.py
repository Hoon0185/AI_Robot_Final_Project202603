import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # 패키지 이름 변수로 설정
    package_name = 'protect_product'

    ros_mode_arg = DeclareLaunchArgument(
        'ros_mode',
        default_value='True',
        description='True=Robot_topic, False=RTSP_bridge'
    )
    ros_mode_config = LaunchConfiguration('ros_mode')

    # 1-1. Product Detector 노드 설정 (YOLO 추론 전문)
    product_detector_node = Node(
        package=package_name,
        executable='product_detector',
        name='product_detector_node',
        output='screen',
        emulate_tty=True,
        parameters=[{'use_sim_time': False, 'ros_mode': ros_mode_config}]
    )

    # 1-2. QR Detector 노드 설정 (QR 스캔 및 전처리 전문)
    qr_detector_node = Node(
        package=package_name,
        executable='qr_detector',
        name='qr_detector_node',
        output='screen',
        emulate_tty=True,
        parameters=[{'use_sim_time': False, 'ros_mode': ros_mode_config}]
    )

    # 2. Verifier 노드 설정 (QR 인식 및 DB 대조)
    verifier_node = Node(
        package=package_name,
        executable='verifier',
        name='verifier_node',
        output='screen',
        emulate_tty=True,
        parameters=[{'ros_mode': ros_mode_config}]
    )

    # 3. Viewer 노드 설정 (최종 GUI 출력)
    viewer_node = Node(
        package=package_name,
        executable='viewer',
        name='viewer_node',
        output='screen',
        emulate_tty=True
    )

    # 4. Camera 노드 설정 (RTSP - RasberryPI)
    camera_node = Node(
        package='protect_product',
        executable='camera_node',
        # RTSP 노드는 ros_mode가 False일 때만 의미가 있으므로 항상 띄워도됨
    )

    # 실행할 노드 리스트 반환
    return LaunchDescription([
        ros_mode_arg,
        product_detector_node,
        qr_detector_node,
        verifier_node,
        camera_node,
        viewer_node
    ])
