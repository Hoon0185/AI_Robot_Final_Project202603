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

        # [1단계] 객체 분류 및 기초 시각화
        for i in range(len(det_msg.class_ids)):
            x1, y1, x2, y2 = max(0, det_msg.x1[i]), max(0, det_msg.y1[i]), min(w, det_msg.x2[i]), min(h, det_msg.y2[i])
            name, cls_id = det_msg.class_names[i], det_msg.class_ids[i]
            obj = {'bbox': (x1, y1, x2, y2), 'name': name, 'id': cls_id + 1}

            if "label" in name.lower() or cls_id == 999:
                labels.append(obj)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 3) # 노란색 굵은 박스
            else:
                products.append(obj)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (180, 180, 180), 1) # 회색 얇은 박스

        # [2단계] 매칭 및 QR 데이터 비교 (핵심 로직)
        if labels and products:
            best_label = max(labels, key=lambda x: (x['bbox'][2]-x['bbox'][0])*(x['bbox'][3]-x['bbox'][1]))
            lx1, ly1, lx2, ly2 = best_label['bbox']

            # 매칭된 물체 찾기
            matched_prod = min(products, key=lambda p: abs((p['bbox'][0]+p['bbox'][2])/2 - (lx1+lx2)/2))

            if matched_prod and abs((matched_prod['bbox'][0]+matched_prod['bbox'][2])/2 - (lx1+lx2)/2) < 150:
                # 2-1. DB 정보 조회
                self.cursor.execute("SELECT product_name, product_id FROM products WHERE product_id=?", (matched_prod['id'],))
                row = self.cursor.fetchone()

                if row:
                    db_name, db_id = row[0], str(row[1])

                    # 2-2. QR 내용 실제 스캔 (비교 기능)
                    roi = frame[ly1:ly2, lx1:lx2]
                    decoded = decode(roi)
                    qr_content = decoded[0].data.decode('utf-8') if decoded else "SCAN_FAIL"

                    # 2-3. 비교 판정 및 시각화
                    if qr_content != "SCAN_FAIL" and db_id in qr_content:
                        result_text = f"[OK] {db_name}"
                        color = (0, 255, 0) # 일치하면 녹색
                    else:
                        result_text = f"[MISMATCH] QR:{qr_content} / DB:{db_id}"
                        color = (0, 0, 255) # 불일치하면 적색

                    # 결과 출력
                    cv2.putText(frame, result_text, (lx1, ly1-15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    cv2.line(frame, (int((lx1+lx2)/2), ly1), (int((matched_prod['bbox'][0]+matched_prod['bbox'][2])/2), matched_prod['bbox'][3]), color, 2)

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
