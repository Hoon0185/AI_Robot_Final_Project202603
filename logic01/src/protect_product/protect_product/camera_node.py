import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from cv_bridge import CvBridge
import cv2
import os
import time

class RtspBridgeNode(Node):
    def __init__(self):
        super().__init__('rtsp_bridge_node')
        self.bridge = CvBridge()

        # [네트워크 안정화] TCP 전송 강제 및 지연 최적화 설정
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        
        # RTSP 설정 (IP 확인 완료)
        self.user, self.pw, self.ip = "robot1", "robot123", "192.168.1.18"
        self.rtsp_url = f"rtsp://{self.user}:{self.pw}@{self.ip}:554/stream1"

        self.cap = None
        self.connect_to_camera()

        self.cam_width = 640
        self.cam_height = 360
        self.last_reconnect_time = time.time()

        # 발행 토픽명을 /rtsp_image로 고정
        self.publisher = self.create_publisher(CompressedImage, '/rtsp_image', 10)

        # [대역폭 최적화] 5 FPS 송출 (데이터 소모량 75% 감소)
        self.fps = 5.0
        self.timer = self.create_timer(1.0 / self.fps, self.timer_callback)
        self.get_logger().info(f'📉 /rtsp_image로 초경량 송출 중 ({self.fps} FPS, TCP 모드)...')

    def connect_to_camera(self):
        """카메라 연결 및 초기화"""
        if self.cap is not None:
            self.cap.release()
        
        self.get_logger().info(f"🔄 IPCAM 연결 시도 중... ({self.ip})")
        self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        if self.cap.isOpened():
            self.get_logger().info("✅ IPCAM 연결 성공!")
        else:
            self.get_logger().error("❌ IPCAM 연결 실패. 재시도 예정.")

    def timer_callback(self):
        # 카메라 연결 상태 확인 및 재접속 로직
        if self.cap is None or not self.cap.isOpened():
            if time.time() - self.last_reconnect_time > 3.0:
                self.connect_to_camera()
                self.last_reconnect_time = time.time()
            return

        # 최신 프레임 획득 (지연 방지용 다중 Grab)
        # 5 FPS이므로 grab 횟수를 줄여 부하 최소화
        for _ in range(2):
            self.cap.grab()
        
        ret, frame = self.cap.retrieve()
        
        if not ret or frame is None:
            # 프레임 수신 실패 시 (네트워크 장애 등)
            self.get_logger().warn("⚠️ 프레임 수신 실패. 3초 후 재연결을 시도합니다.")
            if time.time() - self.last_reconnect_time > 3.0:
                self.connect_to_camera()
                self.last_reconnect_time = time.time()
            return

        # [데이터 경량화] 이미지 크기 조정 및 강력 압축
        resized_frame = cv2.resize(frame, (self.cam_width, self.cam_height))
        
        # [압축률 강화] 품질을 40으로 낮춰 패킷 크기 최적화 (사용자 요청 반영)
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 40]
        _, buffer = cv2.imencode('.jpg', resized_frame, encode_param)
        
        msg = CompressedImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.format = "jpeg"
        msg.data = buffer.tobytes()
        
        self.publisher.publish(msg)
        # self.get_logger().debug("✅ 프레임 발행 완료")

def main(args=None):
    rclpy.init(args=args)
    node = RtspBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.cap:
            node.cap.release()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
