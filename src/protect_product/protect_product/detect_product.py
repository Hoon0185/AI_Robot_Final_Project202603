#기존에 작성했던 코드로 분할 이후 버리는 작업중입니다.
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from cv_bridge import CvBridge
import cv2
from ultralytics import YOLO
import sqlite3
from rclpy.qos import QoSProfile, ReliabilityPolicy
from ament_index_python.packages import get_package_share_directory
import os

class DetectProductNode(Node):
    def __init__(self):
        super().__init__('detect_product_node')

        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT, # 터틀봇 무선 환경 권장
            depth=10
        )

        # 1. 모델 및 DB 초기화 (동적 경로 사용)
        pkg_dir = get_package_share_directory('protect_product')
        model_path = os.path.join(pkg_dir, 'models', 'products.pt')
        db_path = os.path.join(pkg_dir, 'models', 'product.db')
        
        # 소스 경로 대비
        if not os.path.exists(model_path):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(current_dir, '..', 'models', 'products.pt')
            db_path = os.path.join(current_dir, '..', 'models', 'product.db')

        self.model = YOLO(model_path)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.detector = cv2.QRCodeDetector()
        self.bridge = CvBridge()

        # 2. 이미지 구독 (터틀봇 카메라 토픽)
        # v4l2_camera 기본 토픽인 /image_raw를 구독합니다.
        self.subscription = self.create_subscription(
            CompressedImage,
            '/image_raw/compressed',
            self.image_callback,
            qos_profile)

        # 3. 결과 영상 발행 (Control Server나 GUI Client 확인용)
        self.publisher = self.create_publisher(CompressedImage, '/detected_product_image', qos_profile)

        self.get_logger().info('물품 인식 노드 가동.')

    def image_callback(self, msg):
        # ROS Image 메시지를 OpenCV 포맷으로 변환
        frame = self.bridge.compressed_imgmsg_to_cv2(msg, desired_encoding='bgr8')

        # --- 기존 비즈니스 로직 적용 ---
        results = self.model(frame)
        detected_codes = []

        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # ROI 설정 및 QR 인식
            # 과자를 인식한 경우 과자 인식된 범위 기준 세로의 절반만큼 영역에서 바코드를 찾습니다.
            roi = frame[y1:y2 + int((y2 - y1) * 0.5), x1:x2] # ROI 수식 유지
            if roi.size == 0: continue

            data, bbox, _ = self.detector.detectAndDecode(roi)
            if data:
                self.get_logger().info(f"QR 인식 성공: {data}")
                detected_codes.append(data)

            cls_id = int(box.cls[0]) + 1
            class_name = self.model.names[int(box.cls[0])]

            # DB 조회
            # 바코드를 읽고 물품과 비교합니다.
            # product_id=인식을 통해 추려낸 물품 고유번호, detected_codes=바코드로 찍힌 숫자
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

        # 화면 표시 (GUI 띄우기)
        cv2.imshow("YOLO Detection", annotated_frame)
        cv2.waitKey(1)

        # 처리된 영상을 다시 ROS 토픽으로 발행
        result_msg = self.bridge.cv2_to_compressed_imgmsg(annotated_frame, dst_format='jpg')
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
        if rclpy.ok(): # 살아있을 때만 셧다운
            rclpy.shutdown()

if __name__ == '__main__':
    main()
