import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray
from cv_bridge import CvBridge
from ultralytics import YOLO

class ProductDetectorNode(Node):
    def __init__(self):
        super().__init__('product_detector_node')
        # 모델 로드 (YOLO 전용)
        model_path = "/home/bird99/Desktop/database/heavy/products.pt"
        self.model = YOLO(model_path)
        self.bridge = CvBridge()

        # 발행: /det_objs (과자 좌표 전달)
        self.publisher = self.create_publisher(DetectionArray, '/det_objs', 10)
        # 구독: (핑 지연 방지 큐 사이즈 1)
        self.subscription = self.create_subscription(
            CompressedImage, '/image_raw/compressed', self.callback, 1)

        self.get_logger().info('YOLO 물품 인식 노드 가동')

    def callback(self, msg):
        frame = self.bridge.compressed_imgmsg_to_cv2(msg, 'bgr8')
        det_msg = DetectionArray()

        # YOLO 추론
        results = self.model(frame, conf=0.6, iou=0.3, verbose=False)

        for box in results[0].boxes:
            cls_id = int(box.cls[0])  # 모델 클래스 아이디
            cls_name = self.model.names[cls_id].lower() # 모델 클래스 이름
            conf_score = float(box.conf[0]) # 모델 신뢰도
            # 불필요한 클래스 필터링
            if cls_id == 89 or 'backside' in cls_name: continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            self.add_to_msg(det_msg, x1, y1, x2, y2, cls_id, cls_name, conf_score)

        self.publisher.publish(det_msg)

    def add_to_msg(self, msg, x1, y1, x2, y2, cls_id, cls_name, score):
        msg.x1.append(x1); msg.y1.append(y1)
        msg.x2.append(x2); msg.y2.append(y2)
        msg.class_ids.append(cls_id); msg.class_names.append(cls_name)
        # 주의: protect_product_msgs/DetectionArray 메시지에 scores (float32[]) 필드 정의
        if hasattr(msg, 'scores'):
            msg.scores.append(score)
        else:
            # 로그로 출력해서 확인
            self.get_logger().info(f"[{cls_name}] 인식 신뢰도: {score:.2f}")
def main(args=None):
    rclpy.init(args=args)
    node = ProductDetectorNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__':
    main()
