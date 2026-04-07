import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray
from cv_bridge import CvBridge
import cv2
from .qr_detector import QRDetector
from .product_detector import ProductDetector
from .verifier import Verifier

class IntegratedPCNode(Node):
    def __init__(self):
        super().__init__('integrated_pc_node')

        # 1. 단일 비디오 캡처 객체 생성
        self.rtsp_url = "rtsp://robot1:robot123@192.168.1.18:554/stream1"
        self.cap = cv2.VideoCapture(self.rtsp_url)

        # 2. 분석 모듈 객체화
        self.qr_mod = QRDetector()
        self.yolo_mod = ProductDetector()
        self.verifier_mod = Verifier("/home/bird99/Desktop/database/heavy/product.db")
        self.bridge = CvBridge()

        # 3. 상태 및 퍼블리셔 설정
        self.is_waiting_for_ai = False
        self.result_pub = self.create_publisher(DetectionArray, '/verified_objs', 10)

        # 4. 루프 타이머 (모든 인식 과정을 이 안에서 순차 실행)
        self.timer = self.create_timer(0.033, self.process_all)

    def process_all(self):
        ret, frame = self.cap.read()
        if not ret:
            self.cap.open(self.rtsp_url) # 연결 끊김 시 재시도
            return

        # --- [중요] 모든 인식/검증 로직이 동일한 frame을 공유함 ---
        if self.is_waiting_for_ai:
            # Step A: QR 탐지기 실행 (frame 전달)
            qrs = self.qr_mod.detect(frame)

            # Step B: YOLO 탐지기 실행 (frame 전달)
            items = self.yolo_mod.predict(frame)

            # Step C: 검증기 실행 (두 결과값 비교)
            result = self.verifier_mod.verify(qrs, items)

            if result:
                # 결과 데이터 발행 (PatrolNode용)
                self.publish_detection_data(result)

                # 시각화 (frame 위에 직접 그리기)
                self.draw_overlay(frame, result)

        # --- [마지막] 결과가 반영된(혹은 원본) 영상을 GUI용 토픽으로 발행 ---
        msg = self.bridge.cv2_to_compressed_imgmsg(frame)
        self.image_pub.publish(msg)

    def draw_overlay(self, frame, result):
        """인식 결과에 따라 박스와 텍스트를 그리는 헬퍼 함수"""
        color_map = {'정상': (0, 255, 0), '오배열': (0, 0, 255), '결품': (0, 165, 255)}
        color = color_map.get(result['status'], (255, 255, 255))

        if any(result['bbox']):
            cv2.rectangle(frame, (int(result['bbox'][0]), int(result['bbox'][1])),
                          (int(result['bbox'][2]), int(result['bbox'][3])), color, 3)

        cv2.putText(frame, f"{result['status']}: {result['item_name']}", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

def main():
    rclpy.init()
    node = IntegratedPCNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        node.destroy_node()
        rclpy.shutdown()
