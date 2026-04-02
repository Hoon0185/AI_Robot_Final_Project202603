import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray
from cv_bridge import CvBridge
import cv2
import sqlite3
import message_filters
from pyzbar.pyzbar import decode
from rclpy.qos import QoSProfile, ReliabilityPolicy

class VerifierNode(Node):
    def __init__(self):
        super().__init__('verifier_node')
        self.bridge = CvBridge()

        # 1. DB 연결 (PC 로컬 경로)
        db_path = "/home/bird99/Desktop/database/dmdata/product.db"
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()

        # 2. 동기화 설정 (큐 사이즈 축소로 핑 지연 방지)
        qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, depth=5)
        self.img_sub = message_filters.Subscriber(self, CompressedImage, '/image_raw/compressed', qos_profile=qos)
        self.det_sub = message_filters.Subscriber(self, DetectionArray, '/det_objs')
        self.ts = message_filters.ApproximateTimeSynchronizer([self.img_sub, self.det_sub], queue_size=2, slop=0.1, allow_headerless=True)
        self.ts.registerCallback(self.sync_callback)
        self.result_pub = self.create_publisher(DetectionArray, '/verified_objs', 10)
        self.get_logger().info('✅ Verifier: ROI 기반 정밀 스캔 및 시각화 가동')

    def sync_callback(self, img_msg, det_msg):
        frame = self.bridge.compressed_imgmsg_to_cv2(img_msg, 'bgr8')
        h, w, _ = frame.shape
        products, labels = [], []

        # [1단계] 객체 분류
        for i in range(len(det_msg.class_ids)):
            cls_id = det_msg.class_ids[i]
            x1, y1, x2, y2 = max(0, det_msg.x1[i]), max(0, det_msg.y1[i]), min(w, det_msg.x2[i]), min(h, det_msg.y2[i])
            name = det_msg.class_names[i]
            obj = {'bbox': (x1, y1, x2, y2), 'name': name, 'id': cls_id + 1}

            if cls_id == 999 or "label" in name.lower():
                labels.append(obj)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 3)
            else:
                products.append(obj)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (180, 180, 180), 1)

        # [2단계] 판별 로직
        if labels:
            best_label = max(labels, key=lambda x: (x['bbox'][2]-x['bbox'][0])*(x['bbox'][3]-x['bbox'][1]))
            lx1, ly1, lx2, ly2 = best_label['bbox']

            qr_content = None
            roi = frame[ly1:ly2, lx1:lx2]

            if roi.size > 0:
                gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                roi_resized = cv2.resize(gray_roi, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR)
                decoded = decode(roi_resized)

                if decoded:
                    qr_content = decoded[0].data.decode('utf-8')
                else:
                    decoded_retry = decode(gray_roi)
                    if decoded_retry:
                        qr_content = decoded_retry[0].data.decode('utf-8')

            # qr_content가 None이든 아니든 안전한 문자열로 변환
            display_text = str(qr_content).strip() if qr_content is not None else "미인식상태 입니다."

            for i in range(len(det_msg.class_names)):
                if det_msg.class_names[i] == 'label':
                    # 절대로 None이 들어가지 않도록 display_text(문자열)를 대입
                    det_msg.class_names[i] = display_text
            # 인식된 결과 발행
            self.result_pub.publish(det_msg)

            # 과자 매칭
            matched_prod = None
            if products:
                candidate = min(products, key=lambda p: abs((p['bbox'][0]+p['bbox'][2])/2 - (lx1+lx2)/2))
                if abs((candidate['bbox'][0]+candidate['bbox'][2])/2 - (lx1+lx2)/2) < 150:
                    matched_prod = candidate

            # 결과 출력
            if matched_prod:
                self.cursor.execute("SELECT product_name, product_id FROM products WHERE product_id=?", (matched_prod['id'],))
                row = self.cursor.fetchone()
                if row:
                    db_name, db_id = row[0], str(row[1])
                    if qr_content is None: # 스캔 실패
                        txt, color = f"[SCAN FAIL] {db_name}", (0, 165, 255)
                    elif db_id in qr_content: # 일치
                        txt, color = f"[OK] {db_name}", (0, 255, 0)
                    else: # 불일치
                        txt, color = f"[MISMATCH] QR:{qr_content}", (0, 0, 255)

                    cv2.putText(frame, txt, (lx1, ly1-15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    cv2.line(frame, (int((lx1+lx2)/2), ly1), (int((matched_prod['bbox'][0]+matched_prod['bbox'][2])/2), matched_prod['bbox'][3]), color, 2)
            else:
                # 과자가 없는 경우 (EMPTY)
                empty_txt = f"[EMPTY] QR:{qr_content}" if qr_content else "[EMPTY] SCAN FAIL"
                cv2.putText(frame, empty_txt, (lx1, ly1-15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        cv2.imshow("dkdh", frame)
        cv2.waitKey(1)

    def __del__(self):
        cv2.destroyAllWindows()
        if hasattr(self, 'conn'): self.conn.close()

def main(args=None):
    rclpy.init(args=args)
    node = VerifierNode(); rclpy.spin(node)
    node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__':
    main()
