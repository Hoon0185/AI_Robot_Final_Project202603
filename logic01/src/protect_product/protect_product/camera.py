import rclpy
import time
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray, Detection
from cv_bridge import CvBridge
import cv2
import threading # 최신 프레임 유지를 위한 스레드 추가
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

class IntegratedPCNode(Node):
    def __init__(self):
        super().__init__('integrated_pc_node')

        # 1. 단일 비디오 캡처 객체 생성
        self.rtsp_url = "rtsp://robot1:robot123@192.168.1.18:554/stream1"
        self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # 최신 프레임 저장을 위한 변수와 스레드
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.latest_frame = None
        self.last_result = None
        self.capture_thread = threading.Thread(target=self._update_frame, daemon=True)
        self.capture_thread.start()

        # 2. 분석 모듈 객체화
        self.qr_mod = QRDetector()
        self.yolo_mod = ProductDetector()
        self.verifier_mod = Verifier()
        self.bridge = CvBridge()

        # 3. 상태 및 퍼블리셔 설정
        self.is_waiting_for_ai = True
        self.result_pub = self.create_publisher(DetectionArray, '/verified_objs', 10)
        self.detection_start_times = {}
        self.already_logged = {}

        # 4. 루프 타이머 (모든 인식 과정을 이 안에서 순차 실행)
        self.timer = self.create_timer(0.033, self.process_all)
    def _update_frame(self):
        """백그라운드 스레드: 버퍼가 쌓이지 않도록 계속 프레임을 읽어 최신화함"""
        while rclpy.ok():
            if not self.cap.isOpened():
                self.get_logger().warn("카메라 연결 시도 중...")
                self.cap.open(self.rtsp_url)
                time.sleep(2.0)  # 재접속 시도 간격 제한 (세그멘테이션 방지)
                continue

            ret, frame = self.cap.read()
            if ret and frame is not None:
                with self.frame_lock:
                    self.latest_frame = frame
            else:
                # 읽기 실패 시 잠시 대기 후 루프 재개
                self.get_logger().warn("프레임 수신 실패")
                time.sleep(0.5)

    def process_all(self):
        if not self.is_waiting_for_ai: return
        frame = None
        # 최신 프레임을 안전하게 가져오기
        with self.frame_lock:
            if self.latest_frame is not None:
                # frame이 유효한지 다시 한번 확인
                if isinstance(self.latest_frame, (cv2.Mat, object)):
                    frame = self.latest_frame.copy()

        if frame is None or frame.size == 0:
            return # 프레임이 비어있으면 로직 건너뛰기

        # --- [중요] 모든 인식/검증 로직이 동일한 frame을 공유함 ---
        if self.is_waiting_for_ai:
            # Step 1: QR 탐지기 실행 (frame 전달)
            qrs = self.qr_mod.detect(frame)

            # Step 2: YOLO 탐지기 실행 (frame 전달)
            items = self.yolo_mod.predict(frame)

            # Step 3: 검증기 실행 (두 결과값 비교)
            result = self.verifier_mod.verify(qrs, items)

            # 로그 제어 - 실시간 감지 기준으로 2초간 인식된 물품이 동일할 경우 로그 출력
            current_time = time.time()
            active_classes = [item.class_name for item in items]

            self.get_logger().info(f"🎯 [AI 탐지] 바코드: {len(qrs)}개 / 물체: {len(items)}개", throttle_duration_sec=5.0) # 5초마다 로그 출력

            for item in items:
                name = item.class_name  # 탐지된 물품 이름 (영어)
                if name not in self.detection_start_times:
                    self.detection_start_times[name] = current_time
                    self.already_logged[name] = False
                    continue

                # 로그 탐지 시간 제한
                duration = current_time - self.detection_start_times[name]

                if duration >= 2.0 and not self.already_logged[name]:
                    self.get_logger().info(f"🚨 [확인] 탐지된 물품 : {name} (신뢰도: {item.score:.2f})")
                    self.already_logged[name] = True # 한 번만 출력하도록 설정

            # 화면에서 사라진 물체는 메모리에서 삭제
            # 현재 탐지 목록(active_classes)에 없는 이름들을 딕셔너리에서 제거하여
            # 나중에 다시 나타났을 때 처음부터 시간을 잴 수 있게함
            for stored_name in list(self.detection_start_times.keys()):
                if stored_name not in active_classes:
                    del self.detection_start_times[stored_name]
                    if stored_name in self.already_logged:
                        del self.already_logged[stored_name]

            if result:
                frame = self.draw_overlay(frame, result)
                msg = DetectionArray()
                det = Detection()

                # 정보 매핑
                det.class_id = result['class_id']        # 물체 클래스 번호
                det.detected_barcode = result['detected_barcode'] # 인식된 바코드
                det.confidence = result['confidence'] # 신뢰도
                det.status = result['status']         # 정상/오배열 등

                # 결과가 나왔을 때 터미널에 출력
                self.get_logger().info(
                    f"===> [MATCH] 물품 번호: {det.class_id} | "
                    f"물품 이름: {result['item_name']} | "
                    f"인식된 번호: {det.detected_barcode}"
                )
                msg.detections.append(det)
                self.result_pub.publish(msg)

        with self.frame_lock:
            self.latest_frame = frame
    def draw_overlay(self, frame, result):
        if result is None:
            return frame

        # 노란색 (BGR: Blue=0, Green=255, Red=255)
        line_color = (0, 255, 255)
        line_thickness = 2

        # verifier에서 넘겨준 물품의 영역 (x1, y1, x2, y2)
        prod_bbox = result.get('prod_bbox', [0, 0, 0, 0])

        # 영역 값이 유효한 경우에만 그림 (모두 0이 아닌 경우)
        if any(prod_bbox):
            x1, y1, x2, y2 = map(int, prod_bbox)

            # 물품 영역 사각형 그리기
            cv2.rectangle(frame, (x1, y1), (x2, y2), line_color, line_thickness)

            # (선택 사항) 가시성을 위해 물품 이름만 사각형 위에 작게 표시
            label = f"{result['item_name']} ({result['status']})"
            cv2.putText(frame, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, line_color, 2)

        return frame
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
