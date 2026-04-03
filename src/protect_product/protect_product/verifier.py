import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray
from cv_bridge import CvBridge
import cv2, sqlite3, message_filters
from pyzbar.pyzbar import decode

class VerifierNode(Node):
    def __init__(self):
        super().__init__('verifier_node')
        self.bridge = CvBridge()
        self.scan_count = 0
        self.conn = sqlite3.connect("/home/bird99/Desktop/database/dmdata/product.db", check_same_thread=False)
        self.cursor = self.conn.cursor()

        # 동기화 설정
        self.img_sub = message_filters.Subscriber(self, CompressedImage, '/image_raw/compressed')
        self.det_sub = message_filters.Subscriber(self, DetectionArray, '/det_objs')
        self.ts = message_filters.ApproximateTimeSynchronizer([self.img_sub, self.det_sub], queue_size=2, slop=0.2,allow_headerless=True)
        self.ts.registerCallback(self.sync_callback)
        self.result_pub = self.create_publisher(DetectionArray, '/verified_objs', 10)

    def sync_callback(self, img_msg, det_msg):
        frame = self.bridge.compressed_imgmsg_to_cv2(img_msg, 'bgr8')
        h, w, _ = frame.shape
        products, labels = [], []

        for i in range(len(det_msg.class_ids)):
            cls_id = det_msg.class_ids[i]
            x1, y1, x2, y2 = det_msg.x1[i], det_msg.y1[i], det_msg.x2[i], det_msg.y2[i]
            obj = {'bbox': (x1, y1, x2, y2), 'name': det_msg.class_names[i], 'id': cls_id}
            if cls_id == 999 or "label" in obj['name'].lower(): labels.append(obj)
            else: products.append(obj)

        qr_content, matched_prod = None, None
        if labels:
            self.scan_count += 1
            if self.scan_count % 3 == 0: # 3프레임당 1회 스캔
                best_label = max(labels, key=lambda x: (x['bbox'][2]-x['bbox'][0])*(x['bbox'][3]-x['bbox'][1]))
                lx1, ly1, lx2, ly2 = best_label['bbox']
                roi = frame[ly1:ly2, lx1:lx2]
                if roi.size > 0:
                    decoded = decode(cv2.resize(roi, None, fx=1.5, fy=1.5))
                    if decoded: qr_content = decoded[0].data.decode('utf-8').strip()

            # 메시지 업데이트
            for i in range(len(det_msg.class_names)):
                if det_msg.class_names[i] == 'label':
                    det_msg.class_names[i] = str(qr_content) if qr_content else "Scanning..."

            if products:
                lx1, ly1, lx2, ly2 = max(labels, key=lambda x: (x['bbox'][2]-x['bbox'][0])*(x['bbox'][3]-x['bbox'][1]))['bbox']
                candidate = min(products, key=lambda p: abs((p['bbox'][0]+p['bbox'][2])/2 - (lx1+lx2)/2))
                if abs((candidate['bbox'][0]+candidate['bbox'][2])/2 - (lx1+lx2)/2) < 150:
                    matched_prod = candidate

        self.result_pub.publish(det_msg)

        # 시각화 (PC 화면)
        if labels and matched_prod:
            P_id = matched_prod['id'] + 1
            self.cursor.execute("SELECT product_name, product_id FROM products WHERE product_id=?", (P_id,))
            row = self.cursor.fetchone()
            if row:
                color = (0, 255, 0) if qr_content and str(row[1]) in qr_content else (0, 0, 255)
                cv2.putText(frame, f"{row[0]}", (labels[0]['bbox'][0], labels[0]['bbox'][1]-10), 1, 1.5, color, 2)

        cv2.imshow("dkdh", frame); cv2.waitKey(1)

def main(args=None):
    rclpy.init(args=args)
    node = VerifierNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('사용자에 의해 중단됨')
    finally:
        # DB 연결 종료 및 창 닫기 등 자원 정리
        node.cursor.close()
        node.conn.close()
        cv2.destroyAllWindows()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
