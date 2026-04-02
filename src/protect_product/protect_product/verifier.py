import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray
from cv_bridge import CvBridge
import cv2
import sqlite3
import message_filters
from pyzbar.pyzbar import decode  # QR 내용 대조를 위해 추가
from rclpy.qos import QoSProfile, ReliabilityPolicy

class VerifierNode(Node):
    def __init__(self):
        super().__init__('verifier_node')
        self.bridge = CvBridge()

        # 1. DB 연결
        db_path = "/home/bird99/AI_Robot_Final_Project202603/src/protect_product/models/product.db"
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()

        # 2. QoS 및 동기화
        qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, depth=10)
        self.img_sub = message_filters.Subscriber(self, CompressedImage, '/image_raw/compressed', qos_profile=qos)
        self.det_sub = message_filters.Subscriber(self, DetectionArray, '/det_objs')
        self.ts = message_filters.ApproximateTimeSynchronizer([self.img_sub, self.det_sub], 10, 0.8, allow_headerless=True)
        self.ts.registerCallback(self.sync_callback)

        self.publisher = self.create_publisher(CompressedImage, '/verif_img/compressed', qos)
        self.get_logger().info('✅ Verifier: QR 비교 및 시각화 강화 모드 가동')

    def sync_callback(self, img_msg, det_msg):
        frame = self.bridge.compressed_imgmsg_to_cv2(img_msg, 'bgr8')
        h, w, _ = frame.shape
        products, labels = [], []

        # [1단계] 객체 분류 및 노이즈 제거
        for i in range(len(det_msg.class_ids)):
            cls_id = det_msg.class_ids[i]

            # [누락보완 1] 빛 반사로 인한 Backside(89번)는 아예 무시 (인식 리스트에서 제외)
            if cls_id == 89:
                continue

            x1, y1, x2, y2 = max(0, det_msg.x1[i]), max(0, det_msg.y1[i]), min(w, det_msg.x2[i]), min(h, det_msg.y2[i])
            name = det_msg.class_names[i]
            obj = {'bbox': (x1, y1, x2, y2), 'name': name, 'id': cls_id + 1}

            if "label" in name.lower() or cls_id == 999:
                labels.append(obj)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 3) # QR: 노란색 굵게
            else:
                products.append(obj)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (180, 180, 180), 1) # 물체: 회색 얇게

        # [2단계] 판별 로직 (QR이 감지되었을 때)
        if labels:
            best_label = max(labels, key=lambda x: (x['bbox'][2]-x['bbox'][0])*(x['bbox'][3]-x['bbox'][1]))
            lx1, ly1, lx2, ly2 = best_label['bbox']

            # [누락보완 2] 매칭 시도 및 과자 부재(Empty) 판정
            matched_prod = None
            if products:
                candidate = min(products, key=lambda p: abs((p['bbox'][0]+p['bbox'][2])/2 - (lx1+lx2)/2))
                # QR과 과자의 수직 중심선 거리가 150px 이내인 경우만 인정
                if abs((candidate['bbox'][0]+candidate['bbox'][2])/2 - (lx1+lx2)/2) < 150:
                    matched_prod = candidate

            if matched_prod:
                # 2-1. 과자가 정상적으로 매칭된 경우
                self.cursor.execute("SELECT product_name, product_id FROM products WHERE product_id=?", (matched_prod['id'],))
                row = self.cursor.fetchone()

                if row:
                    db_name, db_id = row[0], str(row[1])

                    # QR 영역 전처리 (속도/거리 개선)
                    roi = frame[ly1:ly2, lx1:lx2]
                    if roi.size > 0:
                        roi_resized = cv2.resize(roi, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                        decoded = decode(roi_resized)
                        qr_content = decoded[0].data.decode('utf-8') if decoded else None
                    else:
                        qr_content = None

                    # [누락보완 3] 판정 상태 세분화 (Scan Fail vs OK vs Mismatch)
                    if qr_content is None:
                        # QR은 보이지만 텍스트를 못 읽은 경우 (주황색)
                        result_text, color = f"[SCAN FAIL] {db_name}", (255, 128, 0)
                    elif db_id in qr_content:
                        # DB ID와 QR 텍스트가 일치하는 경우 (녹색)
                        result_text, color = f"[OK] {db_name}", (0, 255, 0)
                    else:
                        # 읽기는 했으나 ID가 다른 경우 (빨간색)
                        result_text, color = f"[MISMATCH] QR:{qr_content} / DB:{db_id}", (0, 0, 255)

                    cv2.putText(frame, result_text, (lx1, ly1-15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    cv2.line(frame, (int((lx1+lx2)/2), ly1), (int((matched_prod['bbox'][0]+matched_prod['bbox'][2])/2), matched_prod['bbox'][3]), color, 2)
            else:
                # [누락보완 4] QR은 있는데 근처에 과자가 없는 경우 (빨간색 EMPTY)
                cv2.putText(frame, "[EMPTY] PRODUCT MISSING", (lx1, ly1-15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        self.publish_frame(frame)

    def publish_frame(self, frame):
        self.publisher.publish(self.bridge.cv2_to_compressed_imgmsg(frame, 'jpg'))

    def __del__(self):
        if hasattr(self, 'conn'): self.conn.close()

def main(args=None):
    rclpy.init(args=args)
    node = VerifierNode(); rclpy.spin(node)
    node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__':
    main()
