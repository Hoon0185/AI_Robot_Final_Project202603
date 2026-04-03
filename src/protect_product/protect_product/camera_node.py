# IP Camera - RasberryPi 변환코드 (안되는 상황 대비)
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from cv_bridge import CvBridge
import cv2

class RtspBridgeNode(Node):
    def __init__(self):
        super().__init__('rtsp_bridge_node')
        self.bridge = CvBridge()

        # RTSP 설정
        USER, PASS, IP = "robot1", "robot123", "192.168.1.18"
        self.rtsp_url = f"rtsp://{USER}:{PASS}@{IP}:554/stream1"

        self.cap = cv2.VideoCapture(self.rtsp_url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # 발행 토픽명을 /rtsp_image로 고정
        self.publisher = self.create_publisher(CompressedImage, '/rtsp_image', 10)

        # 30 FPS 송출
        self.timer = self.create_timer(1.0 / 30.0, self.timer_callback)
        self.get_logger().info('/rtsp_image로 송출 중...')

    def timer_callback(self):
        ret, frame = self.cap.read()
        if ret:
            msg = self.bridge.cv2_to_compressed_imgmsg(frame)
            msg.header.stamp = self.get_clock().now().to_msg()
            self.publisher.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = RtspBridgeNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node(); rclpy.shutdown()


# 터틀봇3 내에 만든 카메라 노드
#1. nano camera_node.py
#2. ===이전 코드 주석풀고 복사 붙이기
#3. chmod +x camera_node.py (권한부여)
#4. 실행 python3 camera_node.py

# import rclpy
# from rclpy.node import Node
# from sensor_msgs.msg import CompressedImage
# import cv2
# from cv_bridge import CvBridge

# class CameraNode(Node):
#     def __init__(self):
#         super().__init__('camera_node')
#         self.bridge = CvBridge()
#         self.publisher = self.create_publisher(CompressedImage, '/image_raw/compressed', 10)
#         self.cap = cv2.VideoCapture(0) # 로봇의 카메라 인덱스
#         self.timer = self.create_timer(0.033, self.timer_callback) # 30fps

#     def timer_callback(self):
#         ret, frame = self.cap.read()
#         if ret:
#             msg = self.bridge.cv2_to_compressed_imgmsg(frame)
#             self.publisher.publish(msg)

# def main():
#     rclpy.init(); node = CameraNode(); rclpy.spin(node)

###=====================================================================###

