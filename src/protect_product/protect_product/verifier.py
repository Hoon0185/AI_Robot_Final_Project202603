import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray
from cv_bridge import CvBridge
import cv2
import sqlite3
import message_filters
import numpy as np
from rclpy.qos import QoSProfile, ReliabilityPolicy

class VerifierNode(Node):
    def __init__(self):
        super().__init__('verifier_node')
        self.bridge = CvBridge()

        # 1. QR 코드 디텍터 (내용 분석용)
        self.qr_detector = cv2.QRCodeDetector()

        # 2. DB 연결 (절대 경로 확인)
        db_path = "/home/bird99/AI_Robot_Final_Project202603/src/protect_product/models/product.db"
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()

        # 3. QoS 및 메시지 동기화 설정
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            depth=10
        )

        # 이미지와 검출 좌표 토픽 구독
        self.img_sub = message_filters.Subscriber(
            self, CompressedImage, '/image_raw/compressed', qos_profile=qos_profile)
        self.det_sub = message_filters.Subscriber(
            self, DetectionArray, '/det_objs')

        # 두 메시지의 시간차를 맞춤 (slop: 0.8초)
        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.img_sub, self.det_sub], queue_size=10, slop=0.8, allow_headerless=True)
        self.ts.registerCallback(self.sync_callback)

        # 4. 결과 영상 발행
        self.publisher = self.create_publisher(
            CompressedImage, '/verif_img/compressed', qos_profile)

        self.get_logger().info('✅ Verifier: 분산 처리 모드 가동 (DB 매칭 및 검증 전용)')

    def sync_callback(self, img_msg, det_msg):
        # 이미지 복원
        frame = self.bridge.compressed_imgmsg_to_cv2(img_msg, desired_encoding='bgr8')
        h, w, _ = frame.shape

        labels = []
        products = []

        # 1. Detector가 보내준 객체들을 라벨(QR)과 물체로 분리
        for i in range(len(det_msg.class_ids)):
            cls_name = det_msg.class_names[i]
            x1, y1 = max(0, det_msg.x1[i]), max(0, det_msg.y1[i])
            x2, y2 = min(w, det_msg.x2[i]), min(h, det_msg.y2[i])

            obj = {
                'bbox': (x1, y1, x2, y2),
                'name': cls_name,
                'id': det_msg.class_ids[i] + 1, # DB ID와 매칭 (0->1)
                'area': (x2 - x1) * (y2 - y1)
            }

            # Detector에서 보낸 999번(OpenCV QR) 혹은 이름에 label이 포함된 경우
            if "label" in cls_name.lower() or "barcode" in cls_name.lower() or det_msg.class_ids[i] == 999:
                labels.append(obj)
            else:
                # 물체 박스는 하단 간섭 방지를 위해 살짝 위로 조정
                y2_clipped = y1 + int((y2 - y1) * 0.8)
                obj['bbox'] = (x1, y1, x2, y2_clipped)
                products.append(obj)

        # 2. 라벨이 없으면 원본 전송 후 종료
        if not labels:
            self.publish_frame(frame)
            return

        # 3. 최적의 라벨(가장 큰 것) 하나 선정 및 QR 읽기
        best_label = max(labels, key=lambda x: x['area'])
        lx1, ly1, lx2, ly2 = best_label['bbox']

        # Detector가 찾아준 박스 영역만 잘라서 QR 내용 추출 (매우 빠름)
        roi = frame[ly1:ly2, lx1:lx2]
        qr_text = None
        if roi.size > 0:
            # 인식률 향상을 위한 전처리
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            qr_text, _, _ = self.qr_detector.detectAndDecode(gray)

        # 4. 위치 기반 매칭 (라벨과 가장 가까운 물체 찾기)
        matched_prod = None
        min_dist = 9999
        for prod in products:
            px1, _, px2, _ = prod['bbox']
            # X축 중심점 간의 거리 계산
            dist = abs((px1 + px2) / 2 - (lx1 + lx2) / 2)
            if dist < min_dist and dist < 130: # 130픽셀 이내 매칭
                min_dist = dist
                matched_prod = prod

        # 5. DB 검증 및 시각화
        if matched_prod:
            self.cursor.execute("SELECT product_name, product_id FROM products WHERE product_id=?", (matched_prod['id'],))
            row = self.cursor.fetchone()

            status, color = self.process_verification(row, qr_text)
            self.draw_result(frame, matched_prod['bbox'], status, color)
            # 라벨 박스도 강조 표시
            cv2.rectangle(frame, (lx1, ly1), (lx2, ly2), color, 2)
        else:
            # 쇼카드만 있고 위에 물건이 없는 경우
            self.draw_result(frame, (lx1, ly1, lx2, ly2), "[EMPTY] Stock Out", (255, 0, 255))

        self.publish_frame(frame)

    def process_verification(self, db_row, qr_text):
        """DB 정보와 QR 텍스트를 대조하여 상태와 색상 반환"""
        if db_row and qr_text:
            db_name, db_id = db_row[0], str(db_row[1])
            # QR 텍스트 안에 DB ID나 이름이 포함되어 있는지 확인
            if db_id in qr_text or qr_text in db_id:
                return f"[OK] {db_name}", (0, 255, 0) # 녹색
            else:
                return f"[ERR] Scan:{qr_text} != DB:{db_id}", (0, 0, 255) # 적색
        elif not qr_text:
            return "[QR FAIL] Reading...", (0, 255, 255) # 황색
        else:
            return "[DB ERR] No Data", (0, 0, 255) # 적색

    def draw_result(self, frame, bbox, text, color):
        x1, y1, x2, y2 = bbox
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    def publish_frame(self, frame):
        res_msg = self.bridge.cv2_to_compressed_imgmsg(frame, dst_format='jpg')
        self.publisher.publish(res_msg)

    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()

def main(args=None):
    rclpy.init(args=args)
    node = VerifierNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
