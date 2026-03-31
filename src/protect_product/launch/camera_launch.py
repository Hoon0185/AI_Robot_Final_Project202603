# 이미지 전송을 위한 런치 파일(구파일,현재 미사용 상태 / 영상이 많이 끊길경우 대체 사용)
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='v4l2_camera',
            executable='v4l2_camera_node',
            name='pi_camera',
            parameters=[{
                'video_device': '/dev/video0',
                'image_size': [640, 480], # 대역폭 절약을 위해 해상도 조절
                'time_per_frame': [1, 30], # 30 FPS
                'camera_frame_id': 'camera_link_optical'
            }]
        )
    ])
