import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray  # 메시지 패키지 이름 확인
from cv_bridge import CvBridge
from ultralytics import YOLO
import cv2
import numpy as np

# [추가] pyzbar 라이브러리 임포트
from pyzbar.pyzbar import decode

class DetectorNode(Node):
    def __init__(self):
        super().__init__('detector_node')
        self.frame_count=0 #과부하 방지, 프레임 제약

        # 1. 모델 로드 (경로 확인 필수)
        model_path="/home/bird99/Desktop/database/heavy/products.pt"
        #model_path = "/home/bird99/AI_Robot_Final_Project202603/src/protect_product/models/products.pt"
        self.model = YOLO(model_path)
        self.bridge = CvBridge()

        # [삭제] 성능 저하의 원인인 OpenCV QRCodeDetector는 더 이상 사용하지 않습니다.
        # self.qr_detector = cv2.QRCodeDetector()

        # 2. 발행자 설정 (좌표 데이터 전송)
        self.publisher = self.create_publisher(DetectionArray, '/det_objs', 10)

        # 3. 구독자 설정 (카메라 이미지 수신)
        self.subscription = self.create_subscription(
            CompressedImage,
            '/image_raw/compressed',
            self.callback,
            10)

        self.get_logger().info('detector : YOLO(물체) + pyzbar(QR)')

    def callback(self, msg):
        # 이미지를 OpenCV 포맷으로 변환
        frame = self.bridge.compressed_imgmsg_to_cv2(msg)
        self.frame_count+=1
        det_msg = DetectionArray()

        # --- [작업 1] YOLO 추론 (물체 감지) ---
        # conf=0.45, iou=0.3 (겹치는 박스를 더 강력하게 제거)
        results = self.model(frame, conf=0.5, iou=0.2)
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            cls_name = self.model.names[cls_id].lower()
            if cls_id == 89 or 'backside' in cls_name: continue # Backside 제외

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            self.add_to_msg(det_msg, x1, y1, x2, y2, cls_id, cls_name)

        # --- [작업 2] pyzbar 강력 QR 검출 (라벨 감지 보완) ---
        if self.frame_count%5==0:
            # pyzbar는 그레이스케일 이미지에서 더 잘 작동할 수 있으므로 변환합니다.
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # [핵심] pyzbar로 QR 코드 디코딩 시도
            decoded_objs = decode(gray)

            for obj in decoded_objs:
                # QR 코드 데이터를 UTF-8로 디코딩
                qr_data = obj.data.decode('utf-8')

                # pyzbar는 rect(left, top, width, height) 형식으로 좌표를 줍니다.
                left, top, width, height = obj.rect

                # Verifier가 인식할 수 있도록 좌표 변환 (x1, y1, x2, y2)
                x1 = int(left)
                y1 = int(top)
                x2 = int(left + width)
                y2 = int(top + height)

                # 안전제한 (Clipping) - 이미지 밖으로 나가지 않게 함
                h, w = gray.shape
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                # Verifier가 인식할 수 있도록 가상의 'label'이라는 이름과 특정 ID(예: 999) 부여
                # 데이터 규격화 : 가상 클래스 (999-Yolo 코드번호, label-QR 코드 데이터)를 할당해 통역해주는 용도
                self.add_to_msg(det_msg, x1, y1, x2, y2, 999, 'label')

                # [디버깅 로그] 이 로그가 뜨면 QR 인식이 성공한 것입니다!
                self.get_logger().error(f"🎯 pyzbar QR 발견: {qr_data}")

            if self.frame_count>100:
                self.frame_count=0

        self.publisher.publish(det_msg)

    def add_to_msg(self, msg, x1, y1, x2, y2, cls_id, cls_name):
        msg.x1.append(x1)
        msg.y1.append(y1)
        msg.x2.append(x2)
        msg.y2.append(y2)
        msg.class_ids.append(cls_id)
        msg.class_names.append(cls_name)

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
