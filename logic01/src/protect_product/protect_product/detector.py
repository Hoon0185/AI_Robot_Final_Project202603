import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray
from cv_bridge import CvBridge
from ultralytics import YOLO
import cv2
from pyzbar.pyzbar import decode
from ament_index_python.packages import get_package_share_directory
import os

class DetectorNode(Node):
    def __init__(self):
        super().__init__('detector_node')
        self.frame_count = 0

        # 1. 모델 로드 (동적 경로 사용)
        pkg_dir = get_package_share_directory('protect_product')
        model_path = os.path.join(pkg_dir, 'models', 'products.pt')
        
        # 만약 설치 경로가 아닌 소스 경로에서 실행 중일 경우 대비
        if not os.path.exists(model_path):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(current_dir, '..', 'models', 'products.pt')
            
        self.model = YOLO(model_path)
        self.bridge = CvBridge()

        # 2. 발행/구독 설정
        self.publisher = self.create_publisher(DetectionArray, '/det_objs', 10)
        self.subscription = self.create_subscription(
            CompressedImage, '/image_raw/compressed', self.callback, 1)

        self.get_logger().info('YOLO(물체) + pyzbar(전체 스캔) 모드')

    def callback(self, msg):
        # 이미지를 OpenCV 포맷으로 변환
        frame = self.bridge.compressed_imgmsg_to_cv2(msg, desired_encoding='bgr8')
        self.frame_count += 1

        # 메시지 생성 및 데이터 담기
        det_msg = DetectionArray()

        # [작업 1] YOLO 추론 (과자만 찾기)
        results = self.model(frame, conf=0.6, iou=0.3, verbose=False)
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            cls_name = self.model.names[cls_id].lower()
            if cls_id == 89 or 'backside' in cls_name: continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            self.add_to_msg(det_msg, x1, y1, x2, y2, cls_id, cls_name)

        # [작업 2] pyzbar 스캔 (모델 학습 안 되어 있어도 찾는 용도)
        # 렉을 줄이기 위해 3프레임마다 한 번만 수행
        if self.frame_count % 4 == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            decoded_objs = decode(gray)
            for obj in decoded_objs:
                left, top, width, height = obj.rect
                # Verifier가 인식할 수 있게 999번 라벨로 전송
                self.add_to_msg(det_msg, left, top, left+width, top+height, 999, 'label')

        if self.frame_count > 100: self.frame_count = 0
        self.publisher.publish(det_msg)

    def add_to_msg(self, msg, x1, y1, x2, y2, cls_id, cls_name):
        msg.x1.append(int(x1)); msg.y1.append(int(y1))
        msg.x2.append(int(x2)); msg.y2.append(int(y2))
        msg.class_ids.append(cls_id); msg.class_names.append(cls_name)

def main(args=None):
    rclpy.init(args=args)
    node = DetectorNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__':
    main()
