import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray  # 메시지 패키지 이름 확인
from cv_bridge import CvBridge
from ultralytics import YOLO
import cv2
import numpy as np

class DetectorNode(Node):
    def __init__(self):
        super().__init__('detector_node')

        # 1. 모델 로드 (경로 확인 필수)
        model_path = "/home/bird99/AI_Robot_Final_Project202603/src/protect_product/models/products.pt"
        self.model = YOLO(model_path)
        self.bridge = CvBridge()
        self.qr_detector = cv2.QRCodeDetector()

        # 2. 발행자 설정 (좌표 데이터 전송)
        self.publisher = self.create_publisher(DetectionArray, '/det_objs', 10)

        # 3. 구독자 설정 (카메라 이미지 수신)
        self.subscription = self.create_subscription(
            CompressedImage,
            '/image_raw/compressed',
            self.callback,
            10)

        self.get_logger().info('Detector 노드가 가동되었습니다. YOLO 추론을 시작합니다.')

    def callback(self, msg):
        # 이미지를 OpenCV 포맷으로 변환
        frame = self.bridge.compressed_imgmsg_to_cv2(msg)
        det_msg = DetectionArray()

        # --- [작업 1] YOLO 추론 (물체 감지) ---
        results = self.model(frame, conf=0.45, iou=0.5)
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            if cls_id == 89: continue # Backside 제외

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            self.add_to_msg(det_msg, x1, y1, x2, y2, cls_id, self.model.names[cls_id])

        # --- [작업 2] OpenCV QR 직접 검출 (라벨 감지 보완) ---
        # YOLO가 라벨을 못 찾을 경우를 대비해 직접 QR 위치를 추출
        data, points, _ = self.qr_detector.detectAndDecode(frame)
        if data and points is not None:
            pts = points[0].astype(int)
            lx1, ly1 = np.min(pts, axis=0)
            lx2, ly2 = np.max(pts, axis=0)

            # Verifier가 인식할 수 있도록 'label'이라는 이름과 특정 ID(예: 999) 부여
            self.add_to_msg(det_msg, int(lx1), int(ly1), int(lx2), int(ly2), 999, 'label')
            self.get_logger().info(f"📍 QR 발견(Detector): {data}")

        self.publisher.publish(det_msg)

    def add_to_msg(self, msg, x1, y1, x2, y2, cls_id, cls_name):
        msg.x1.append(x1)
        msg.y1.append(y1)
        msg.x2.append(x2)
        msg.y2.append(y2)
        msg.class_ids.append(cls_id)
        msg.class_names.append(cls_name)

# 이 부분이 누락되었거나 이름이 main이 아니면 에러가 납니다!
def main(args=None):
    rclpy.init(args=args)
    node = DetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
