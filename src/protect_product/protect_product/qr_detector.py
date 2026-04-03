import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray
from cv_bridge import CvBridge
from pyzbar.pyzbar import decode
import cv2
import numpy as np

class QrDetectorNode(Node):
    def __init__(self):
        super().__init__('qr_detector_node')
        self.bridge = CvBridge()
        self.frame_count = 0

        # 발행: /qr_objs (좌표뿐만 아니라 '텍스트'도 담김)
        self.publisher = self.create_publisher(DetectionArray, '/qr_objs', 10)
        self.subscription = self.create_subscription(
            CompressedImage, '/image_raw/compressed', self.callback, 1)

        self.get_logger().info('QR 전처리 및 해석 노드 가동')

    def callback(self, msg):
        self.frame_count += 1
        if self.frame_count % 2 != 0: return # 연산 부하 조절

        frame = self.bridge.compressed_imgmsg_to_cv2(msg)
        det_msg = DetectionArray()

        # [1] 전처리: 그레이스케일 -> 선명화 (샤프닝)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # [2] 이진화 처리 (QR 코드를 더 선명하게) 블러로 노이즈 제거 후 이진화
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # [3] QR 디코딩 (전처리된 이미지 사용)
        decoded_objs = decode(thresh)

        # 만약 이진화에서 실패하면 원본에서도 시도
        if not decoded_objs:
            decoded_objs = decode(gray)

        for obj in decoded_objs:
            # 확대한 좌표를 원본 크기로 복원 (2.0으로 나눔)
            left, top, width, height = obj.rect

            # QR 내용 추출 (바이트 -> 문자열)
            qr_text = obj.data.decode('utf-8').strip()

            # [핵심] Verifier로 데이터 전송
            # class_id는 999로 고정, class_names에 QR의 실제 텍스트 내용을 담음!
            self.add_to_msg(det_msg, left, top, left+width, top+height, 999, qr_text)

        if self.frame_count > 100: self.frame_count = 0
        self.publisher.publish(det_msg)

    def add_to_msg(self, msg, x1, y1, x2, y2, cls_id, content):
        msg.x1.append(x1); msg.y1.append(y1)
        msg.x2.append(x2); msg.y2.append(y2)
        msg.class_ids.append(cls_id)
        msg.class_names.append(content) # 'label' 대신 'QR내용'이 들어감

def main(args=None):
    rclpy.init(args=args)
    node = QrDetectorNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node(); rclpy.shutdown()
