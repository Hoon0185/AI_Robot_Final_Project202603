# 터틀봇3 내에 만든 카메라 노드
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
import cv2
from cv_bridge import CvBridge

class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        self.bridge = CvBridge()
        self.publisher = self.create_publisher(CompressedImage, '/image_raw/compressed', 10)
        self.cap = cv2.VideoCapture(0) # 로봇의 카메라 인덱스
        self.timer = self.create_timer(0.033, self.timer_callback) # 30fps

    def timer_callback(self):
        ret, frame = self.cap.read()
        if ret:
            msg = self.bridge.cv2_to_compressed_imgmsg(frame)
            self.publisher.publish(msg)

def main():
    rclpy.init(); node = CameraNode(); rclpy.spin(node)
