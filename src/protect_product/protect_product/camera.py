# 이미지 전처리 과정이 아닌 단순 이미지만 추출하는 코드
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage # 기존 노드들과 호환성을 위해 유지
from cv_bridge import CvBridge
import cv2


class RtspPublisher(Node):
    def __init__(self):
        super().__init__('rtsp_publisher')

        # 1. 발행자 설정 (rtsp_image 토픽 사용)
        self.publisher_ = self.create_publisher(CompressedImage, '/rtsp_image', 10)
        self.bridge = CvBridge()

        # 2. RTSP 연결 및 최적화
        rtsp_url = "rtsp://robot1:robot123@192.168.1.18:554/stream1"
        self.cap = cv2.VideoCapture(rtsp_url)

        # [중요] 버퍼를 1로 설정하여 지연(Latency) 최소화
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not self.cap.isOpened():
            self.get_logger().error("RTSP 카메라 연결 실패!")
            return

        # 3. 타이머 설정 (FPS 33 -> 약 0.03초 주기)
        self.timer = self.create_timer(0.03, self.timer_callback)
        self.get_logger().info('고속 스트리밍 시작: /rtsp_image (600x450)')

    def timer_callback(self):
        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().warn("프레임을 읽을 수 없습니다.")
            return

        # 4. 즉시 리사이징 (연산 부하 최소화)
        resized_frame = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)

        cv2.imshow("RTSP Monitor", resized_frame)
        cv2.waitKey(1)

        # 5. 압축 이미지로 변환 (전송 속도 향상)
        msg = self.bridge.cv2_to_compressed_imgmsg(resized_frame)
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "camera_link"

        self.publisher_.publish(msg)

    def __del__(self):
        if self.cap.isOpened():
            self.cap.release()

def main(args=None):
    rclpy.init(args=args)
    node = RtspPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

# [필수] 실행 진입점
if __name__ == '__main__':
    main()
