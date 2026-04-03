import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray
from cv_bridge import CvBridge
from ultralytics import YOLO
from ament_index_python.packages import get_package_share_directory
import os

class DetectorNode(Node):
    def __init__(self):
        super().__init__('detector_node')

        # 1. 모델 로드 (동적 경로 사용)
        pkg_dir = get_package_share_directory('protect_product')
        model_path = os.path.join(pkg_dir, 'models', 'products.pt')
        
        # 만약 설치 경로가 아닌 소스 경로에서 실행 중일 경우 대비
        if not os.path.exists(model_path):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(current_dir, '..', 'models', 'products.pt')
            
        self.model = YOLO(model_path)
        self.bridge = CvBridge()

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
        frame = self.bridge.compressed_imgmsg_to_cv2(msg, desired_encoding='bgr8')

        # YOLO 추론
        results = self.model(frame)

        # 메시지 생성 및 데이터 담기
        det_msg = DetectionArray()
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            det_msg.x1.append(x1)
            det_msg.y1.append(y1)
            det_msg.x2.append(x2)
            det_msg.y2.append(y2)

            # 클래스 ID와 이름 추가
            cls_id = int(box.cls[0])
            det_msg.class_ids.append(cls_id)
            det_msg.class_names.append(self.model.names[cls_id])

        # 발행
        self.publisher.publish(det_msg)

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
