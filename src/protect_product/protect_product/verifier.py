import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray
from cv_bridge import CvBridge
import cv2, sqlite3, message_filters

class VerifierNode(Node):
    def __init__(self):
        super().__init__('verifier_node')
        self.bridge = CvBridge()

        self.declare_parameter('ros_mode', True) # 기본값은 로봇 모드
        ros_mode = self.get_parameter('ros_mode').value

        # 카메라 모드에 따라 토픽 설정
        if ros_mode:
            self.topic_name = '/image_raw/compressed' # 로봇 토픽
        else:
            self.topic_name = '/rtsp_image'           # RTSP 브릿지 토픽

        # 1. 데이터베이스 연결
        db_path = "/home/bird99/Desktop/database/dmdata/product.db"
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()

        # [필수] 최종 검증 결과를 Viewer로 보낼 Publisher
        self.result_pub = self.create_publisher(DetectionArray, '/verified_objs', 10)

        # 2. 3중 동기화 설정 (이미지, YOLO 결과, QR 결과)
        self.img_sub = message_filters.Subscriber(self, CompressedImage, self.topic_name)
        self.det_sub = message_filters.Subscriber(self, DetectionArray, '/det_objs')
        self.qr_sub = message_filters.Subscriber(self, DetectionArray, '/qr_objs')

        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.img_sub, self.det_sub, self.qr_sub],
            queue_size=30,   # 큐 사이즈 증설로 데이터 유실 방지
            slop=1.0,        # 동기화 허용 오차를 1초로 완화 (YOLO 연산 지연 고려)
            allow_headerless=True
        )
        self.ts.registerCallback(self.sync_callback)

        self.get_logger().info('✅ [Verifier] 검증 모드 가동: YOLO ID vs QR Text 대조 시작')

    def sync_callback(self, img_msg, det_msg, qr_msg):
        # 이미지 복원 (YOLO와 동일하게 bgr8 권장)
        frame = self.bridge.compressed_imgmsg_to_cv2(img_msg, 'bgr8')

        matched_qr_content = None
        best_qr_bbox = None

        # 발행용 메시지 객체 생성
        verified_msg = DetectionArray()

        # [단계 1] 화면에서 가장 큰(가까운) QR 코드 찾기
        if len(qr_msg.class_ids) > 0:
            max_area = 0
            for i in range(len(qr_msg.class_ids)):
                area = (qr_msg.x2[i] - qr_msg.x1[i]) * (qr_msg.y2[i] - qr_msg.y1[i])
                if area > max_area:
                    max_area = area
                    best_qr_bbox = (qr_msg.x1[i], qr_msg.y1[i], qr_msg.x2[i], qr_msg.y2[i])
                    matched_qr_content = qr_msg.class_names[i]

            if best_qr_bbox:
                qx1, qy1, qx2, qy2 = best_qr_bbox
                cv2.rectangle(frame, (qx1, qy1), (qx2, qy2), (0, 255, 255), 3) # 노란색 QR 박스
                cv2.putText(frame, f"QR: {matched_qr_content}", (qx1, qy1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # [단계 2] QR과 가장 인접한 YOLO 물품 매칭 및 DB 검증
        if best_qr_bbox and len(det_msg.class_ids) > 0:
            q_cx = (best_qr_bbox[0] + best_qr_bbox[2]) / 2
            min_dist = 9999
            matched_idx = -1

            for i in range(len(det_msg.class_ids)):
                p_cx = (det_msg.x1[i] + det_msg.x2[i]) / 2
                dist = abs(p_cx - q_cx)
                if dist < min_dist:
                    min_dist = dist
                    matched_idx = i

            # 매칭 허용 거리 (200px) 이내인 경우만 진행
            if matched_idx != -1 and min_dist < 200:
                mx1, my1, mx2, my2 = det_msg.x1[matched_idx], det_msg.y1[matched_idx], \
                                     det_msg.x2[matched_idx], det_msg.y2[matched_idx]

                # ROI 시각화용 (85% 크기)
                cx, cy = (mx1 + mx2) / 2, (my1 + my2) / 2
                nw, nh = (mx2 - mx1) * 0.85, (my2 - my1) * 0.85
                dx1, dy1, dx2, dy2 = int(cx - nw/2), int(cy - nh/2), int(cx + nw/2), int(cy + nh/2)

                # --- 핵심 DB 검증 로직 ---
                yolo_cls_id = det_msg.class_ids[matched_idx]
                yolo_product_id = yolo_cls_id + 1  # 모델 ID(0) -> DB ID(1) 보정

                self.cursor.execute("SELECT product_name, product_id FROM products WHERE product_id=?", (yolo_product_id,))
                row = self.cursor.fetchone()

                final_name = det_msg.class_names[matched_idx]
                is_correct = False

                if row:
                    db_name, db_id_val = row[0], str(row[1])
                    final_name = db_name

                    # 설계 내용: QR 텍스트 안에 DB에서 불러온 ID 숫자가 포함되어 있는가?
                    if matched_qr_content and (db_id_val in matched_qr_content):
                        is_correct = True

                # 검증 결과에 따른 색상 결정 (일치: 녹색, 불일치: 적색)
                color = (0, 255, 0) if is_correct else (0, 0, 255)

                cv2.rectangle(frame, (dx1, dy1), (dx2, dy2), color, 2)
                cv2.putText(frame, f"MATCH: {final_name}", (mx1, my1 - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

                # --- Viewer로 전송할 메시지 데이터 구축 ---
                verified_msg.x1.append(int(mx1)); verified_msg.y1.append(int(my1))
                verified_msg.x2.append(int(mx2)); verified_msg.y2.append(int(my2))
                verified_msg.class_ids.append(yolo_cls_id)
                verified_msg.class_names.append(final_name)

                if hasattr(det_msg, 'scores') and len(det_msg.scores) > matched_idx:
                    verified_msg.scores.append(det_msg.scores[matched_idx])
                else:
                    verified_msg.scores.append(0.0)

        elif best_qr_bbox and len(det_msg.class_ids) == 0:
            cv2.putText(frame, "STATUS: EMPTY (No Product)", (30, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 165, 255), 2)

        # Viewer UI를 위해 인식된 QR 정보도 전송 (ID 999 고정)
        if matched_qr_content:
            verified_msg.class_ids.append(999)
            verified_msg.class_names.append(matched_qr_content)
            verified_msg.x1.append(0); verified_msg.y1.append(0)
            verified_msg.x2.append(0); verified_msg.y2.append(0)
            verified_msg.scores.append(1.0)

        # 결과 메시지 최종 발행
        self.result_pub.publish(verified_msg)

        # 결과 화면 출력
        cv2.imshow("Inventory Verification System", frame)
        cv2.waitKey(1)

def main(args=None):
    rclpy.init(args=args)
    node = VerifierNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cursor.close()
        node.conn.close()
        cv2.destroyAllWindows()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
