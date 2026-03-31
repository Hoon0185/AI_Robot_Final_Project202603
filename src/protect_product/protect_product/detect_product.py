import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
from ultralytics import YOLO
import sqlite3
import os

class DetectProductNode(Node):
    def __init__(self):
        super().__init__('detect_product_node')

        # 1. 모델 및 DB 초기화 (기존 main의 설정 부분)
        # 경로 주의: 절대 경로를 사용하거나 패키지 내 리소스 경로를 사용하세요.
        self.model = YOLO("best.pt")
        self.conn = sqlite3.connect("product.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.detector = cv2.QRCodeDetector()
        self.bridge = CvBridge()

        # 2. 이미지 구독 (터틀봇 카메라 토픽)
        # v4l2_camera 기본 토픽인 /image_raw를 구독합니다.
        self.subscription = self.create_subscription(
            Image,
            '/image_raw',
            self.image_callback,
            10) # 큐 사이즈

        # 3. 결과 영상 발행 (Control Server나 GUI Client 확인용)
        self.publisher = self.create_publisher(Image, '/detected_product_image', 10)

        self.get_logger().info('터틀봇 기반 물품 인식 노드가 가동되었습니다.')

    def image_callback(self, msg):
        # ROS Image 메시지를 OpenCV 포맷으로 변환
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

        # --- 기존 비즈니스 로직 적용 ---
        results = self.model(frame)
        detected_codes = []

        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # ROI 설정 및 QR 인식
            roi = frame[y1:y2 + int((y2 - y1) * 0.5), x1:x2] # ROI 수식 유지
            if roi.size == 0: continue

            data, bbox, _ = self.detector.detectAndDecode(roi)
            if data:
                self.get_logger().info(f"QR 인식 성공: {data}")
                detected_codes.append(data)

            cls_id = int(box.cls[0]) + 1
            class_name = self.model.names[int(box.cls[0])]

            # DB 조회
            self.cursor.execute("SELECT * FROM products WHERE product_id=?", (cls_id,))
            rows = self.cursor.fetchall()

            for row in rows:
                product_id = str(row[0])
                if product_id in detected_codes:
                    self.get_logger().info(f"[OK] {class_name} - 일치")
                else:
                    self.get_logger().warn(f"[경고] {class_name} - 불일치")

        # 시각화 및 결과 송신
        annotated_frame = results[0].plot()

        # 화면 표시 (서버에서 GUI를 띄울 때만 사용)
        cv2.imshow("YOLO Detection", annotated_frame)
        cv2.waitKey(1)

        # 처리된 영상을 다시 ROS 토픽으로 발행
        result_msg = self.bridge.cv2_to_imgmsg(annotated_frame, encoding="bgr8")
        self.publisher.publish(result_msg)

    def __del__(self):
        self.conn.close()
        cv2.destroyAllWindows()

def main(args=None):
    rclpy.init(args=args)
    node = DetectProductNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
