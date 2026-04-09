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
        self.rtsp_url = f"rtsp://robot1:robot123@192.168.1.18:554/stream1"

        self.cap = cv2.VideoCapture(self.rtsp_url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.cam_width = 640
        self.cam_height = 360

        # 발행 토픽명을 /rtsp_image로 고정
        self.publisher = self.create_publisher(CompressedImage, '/rtsp_image', 10)

        # 20 FPS 송출 (45 FPS는 Wi-Fi 대역폭에 너무 부담을 줍니다)
        self.timer = self.create_timer(1.0 / 20.0, self.timer_callback)
        self.get_logger().info('/rtsp_image로 최적화 송출 중 (20 FPS)...')

    def timer_callback(self):
        # [최적화] 누적된 지연 방지를 위해 버퍼에 있는 이전 프레임들을 모두 읽어서 버림
        # 오직 가장 최신 프레임만 발행합니다.
        last_frame = None
        while True:
            grabbed = self.cap.grab()
            if not grabbed:
                break
            
            # 다음 프레임이 있는지 확인 (있으면 계속 grab해서 최신으로 이동)
            ret, frame = self.cap.retrieve()
            if ret:
                last_frame = frame
        
        # 가장 최신 프레임만 발행
        if last_frame is not None:
            resized_frame = cv2.resize(last_frame, (self.cam_width, self.cam_height))
            
            # JPEG 품질 설정 (80) 및 CompressedImage 변환
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            _, buffer = cv2.imencode('.jpg', resized_frame, encode_param)
            
            msg = CompressedImage()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.format = "jpeg"
            msg.data = buffer.tobytes()
            
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

