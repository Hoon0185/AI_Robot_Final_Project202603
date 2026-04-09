import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray, Detection
from cv_bridge import CvBridge
import cv2
from .qr_detector import QRDetector
from .product_detector import ProductDetector
from .verifier import Verifier

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class DetectionResult:
    # 공통: 영역 (QR도 영역이 있습니다)
    box: List[int] = field(default_factory=lambda: [0, 0, 0, 0]) # [x1, y1, x2, y2]

    # YOLO 전용 - 클래스ID, 클래스이름(모델에 등록된 영문), 신뢰도
    class_id: Optional[int] = None
    class_name: str = "Unknown"
    score: float = 0.0

    # QR 전용 (인식된 내용)
    raw_data: str = ""

    # DB 비교 결과 (클래스 아이디를 받고 verifier에서 해당 아이디에 해당하는 QRcode(barcode)번호를 받아옴)
    is_verified: bool = False
class IntegratedPCNode(Node):
    def __init__(self):
        super().__init__('integrated_pc_node')

        # [최적화] 직접 RTSP를 열지 않고, camera_node가 발행하는 이미지를 구독합니다.
        # 이를 통해 전체 시스템의 네트워크 대역폭 점유를 획기적으로 줄입니다.
        self.subscription = self.create_subscription(
            CompressedImage,
            '/rtsp_image',
            self.image_callback,
            10)
            
        self.latest_frame = None

        # 2. 분석 모듈 객체화
        self.qr_mod = QRDetector()
        self.yolo_mod = ProductDetector()
        self.verifier_mod = Verifier()
        self.bridge = CvBridge()

        # 3. 상태 및 퍼블리셔 설정
        self.is_waiting_for_ai = True
        self.result_pub = self.create_publisher(DetectionArray, '/verified_objs', 10)

        # 4. 루프 타이머 (AI 연산은 부하가 크므로 10 FPS로 유지)
        self.timer = self.create_timer(1.0 / 10.0, self.process_all)

    def image_callback(self, msg):
        """이미지 수신 시 최신 프레임 업데이트"""
        try:
            import numpy as np
            np_arr = np.frombuffer(msg.data, np.uint8)
            self.latest_frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            self.get_logger().error(f"이미지 수신 에러: {e}")

    def process_all(self):
        if not self.is_waiting_for_ai or self.latest_frame is None:
            return
        
        frame = self.latest_frame.copy()
        # 사용한 프레임은 비워서 중복 처리 방지 (옵션)
        # self.latest_frame = None 

        # --- [중요] 모든 인식/검증 로직이 동일한 frame을 공유함 ---
        if self.is_waiting_for_ai:
            # Step 1: QR 탐지기 실행 (frame 전달)
            qrs = self.qr_mod.detect(frame)

            # Step 2: YOLO 탐지기 실행 (frame 전달)
            items = self.yolo_mod.predict(frame)

            # Step 3: 검증기 실행 (두 결과값 비교)
            result = self.verifier_mod.verify(qrs, items)

            self.get_logger().info(f"🎯 [AI 탐지] 바코드: {len(qrs)}개 / 물체: {len(items)}개")
            for item in items:
                self.get_logger().info(f"   ㄴ 탐지됨: {item.class_name} (신뢰도: {item.score:.2f})")

            if result:
                msg = DetectionArray()
                det = Detection()

                # 요구하신 정보 매핑
                det.class_id = int(result.get('yolo_id', -1))       # 물체 클래스 번호
                det.detected_barcode = result.get('barcode', 'NONE') # 인식된 바코드
                det.confidence = float(result.get('confidence', 0.0)) # 신뢰도
                det.status = result.get('status', 'Unknown')        # 정상/오배열 등

                # 결과가 나왔을 때 터미널에 출력
                self.get_logger().info(f"===> [DETECTED] {result['item_name']} | Status: {result['status']}")

                msg.detections.append(det)
                self.result_pub.publish(msg)

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
