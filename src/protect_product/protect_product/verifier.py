import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product.msg import DetectionArray
from cv_bridge import CvBridge
import cv2
import sqlite3
import message_filters
from rclpy.qos import QoSProfile, ReliabilityPolicy

class VerifierNode(Node):
    def __init__(self):
        super().__init__('verifier_node')
        self.bridge = CvBridge()

        # 1. DB 연결 (절대 경로 사용 권장)
        db_path = "/home/bird99/AI_Robot_Final_Project202603/src/protect_product/models/product.db"
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.detector = cv2.QRCodeDetector()

        # 2. QoS 설정 (터틀봇 환경)
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            depth=10
        )

        # 3. 메시지 필터 설정 (이미지와 좌표 동기화)
        # 각 토픽을 구독하는 서브스크라이버 생성
        self.img_sub = message_filters.Subscriber(
            self, CompressedImage, '/image_raw/compressed', qos_profile=qos_profile)
        self.det_sub = message_filters.Subscriber(
            self, DetectionArray, '/det_objs')

        # 두 메시지의 시간차를 고려하여 동기화 (슬롭 0.1초 설정)
        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.img_sub, self.det_sub], queue_size=10, slop=0.1)
        self.ts.registerCallback(self.sync_callback)

        # 4. 검증 결과 이미지 발행
        self.publisher = self.create_publisher(
            CompressedImage, '/verif_img/compressed', qos_profile)

        self.get_logger().info('Verifier 노드 가동: QR 인식 및 DB 대조를 시작합니다.')

    def sync_callback(self, img_msg, det_msg):
        # 압축 이미지 복원
        frame = self.bridge.compressed_imgmsg_to_cv2(img_msg, desired_encoding='bgr8')
        detected_codes = []

        # 검출된 모든 객체 루프 (DetectionArray 메시지 구조 사용)
        for i in range(len(det_msg.class_ids)):
            x1, y1, x2, y2 = det_msg.x1[i], det_msg.y1[i], det_msg.x2[i], det_msg.y2[i]
            class_name = det_msg.class_names[i]
            cls_id = det_msg.class_ids[i] + 1  # DB ID 매칭을 위해 +1

            # ROI 추출 (물체 하단 50% 영역에서 QR 탐색)
            roi_h_start = y2
            roi_h_end = y2 + int((y2 - y1) * 0.5)
            roi = frame[roi_h_start:roi_h_end, x1:x2]

            if roi.size == 0:
                continue

            # QR 코드 인식
            data, bbox, _ = self.detector.detectAndDecode(roi)

            status_text = "Checking..."
            color = (255, 255, 0) # Cyan (대기)

            if data:
                self.get_logger().info(f"QR 발견: {data}")
                detected_codes.append(data)

                # DB 조회 및 비교
                self.cursor.execute("SELECT * FROM products WHERE product_id=?", (cls_id,))
                row = self.cursor.fetchone()

                if row:
                    product_id_from_db = str(row[0])
                    if product_id_from_db == data:
                        status_text = f"[OK] {class_name}"
                        color = (0, 255, 0) # Green
                        self.get_logger().info(f"{class_name}: 일치 확인")
                    else:
                        status_text = f"[ERR] {class_name} Mismatch"
                        color = (0, 0, 255) # Red
                        self.get_logger().warn(f"{class_name}: 불일치 발생!")

            # 시각화: BBox 및 상태 텍스트 그리기
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, status_text, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # 최종 가공된 이미지를 전송
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
