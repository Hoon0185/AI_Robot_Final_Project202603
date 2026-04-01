import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray
from cv_bridge import CvBridge
import cv2
import sqlite3
import message_filters
from rclpy.qos import QoSProfile, ReliabilityPolicy

class VerifierNode(Node):
    def __init__(self):
        super().__init__('verifier_node')
        self.bridge = CvBridge()

        # 1. DB 연결 (절대 경로 사용 권장)
        db_path = "/home/bird99/AI_Robot_Final_Project202603/src/protect_product/models/product.db"
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.detector = cv2.QRCodeDetector()

        # 2. QoS 설정 (터틀봇 환경)
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            depth=10
        )

        # 3. 메시지 필터 설정 (이미지와 좌표 동기화)
        # 각 토픽을 구독하는 서브스크라이버 생성
        self.img_sub = message_filters.Subscriber(
            self, CompressedImage, '/image_raw/compressed', qos_profile=qos_profile)
        self.det_sub = message_filters.Subscriber(
            self, DetectionArray, '/det_objs')

        # 두 메시지의 시간차를 고려하여 동기화 (슬롭 0.1초 설정)
        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.img_sub, self.det_sub], queue_size=10, slop=0.8, allow_headerless=True)
        self.ts.registerCallback(self.sync_callback)

        # 4. 검증 결과 이미지 발행
        self.publisher = self.create_publisher(
            CompressedImage, '/verif_img/compressed', qos_profile)

        self.get_logger().info('Verifier Node : QR 인식 및 DB 대조 시작')

    def sync_callback(self, img_msg, det_msg):
        # 1. 이미지 복원 및 화면 크기 획득
        # 테스트를 위해 임시적으로 사이즈 줄임, 시현때는 full_frame떼고 frame으로 그대로
        frame = self.bridge.compressed_imgmsg_to_cv2(img_msg, desired_encoding='bgr8')
        h, w, _ = frame.shape

        products = []
        labels = []

        # 2. 객체 분류 및 좌표 안전제한 (Clipping)
        for i in range(len(det_msg.class_ids)):
            # 좌표가 화면 밖으로 나가지 않도록 제한 (에러 방지)
            x1 = max(0, det_msg.x1[i])
            y1 = max(0, det_msg.y1[i])
            x2 = min(w, det_msg.x2[i])
            y2 = min(h, det_msg.y2[i])

            # [과적합 대응] 물체 박스가 너무 커서 바코드를 가린다면 y2를 10% 정도 올림
            # y2 = y2 - int((y2 - y1) * 0.1)

            obj = {
                'bbox': (x1, y1, x2, y2),
                'name': det_msg.class_names[i],
                'id': det_msg.class_ids[i] + 1, # DB product_id와 매칭 (0->1, 1->2 ...)
                'matched': False,
                'qr_data':None
            }

            if obj['name'] == 'backside': continue

            # YOLO가 찾은 바코드(쇼카드) 라벨인지, 실제 물건인지 분류
            if "label" in obj['name'] or "barcode" in obj['name']:
                roi = frame[y1:y2, x1:x2] # 바코드 영역 잘라내기
                if roi.size > 0:
                    # 필요 시 이미지 전처리 (흑백 전환 등)
                    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                    data, _, _ = self.detector.detectAndDecode(gray_roi)
                    if data:
                        obj['qr_data'] = data
                        self.get_logger().info(f"QR 스캔 성공: {data}")
                labels.append(obj)
            else:
                products.append(obj)

        # 3. 위치 기반 매칭 및 DB 검증 로직
        for label in labels:
            lx1, ly1, lx2, ly2 = label['bbox']
            matched_product = None

            for prod in products:
                px1, py1, px2, py2 = prod['bbox']

                # [매칭 조건] X축 중심 거리 60픽셀 이내 AND Y축 간격(물체하단-라벨상단) 130픽셀 이내
                # abs()를 사용하여 박스가 서로 겹치더라도 매칭되도록 설정
                if abs(px1 - lx1) < 60 and abs(ly1 - py2) < 130:
                    matched_product = prod
                    prod['matched'] = True
                    #label['matched'] = True
                    break

            if matched_product:
                # [핵심] DB에서 실제 상품명 조회
                self.cursor.execute("SELECT product_name, product_id FROM products WHERE product_id=?", (matched_product['id'],))
                row = self.cursor.fetchone()

                if row and label['qr_data']:
                    db_name = row[0]
                    # [변경] YOLO 이름 대신 실제 'QR 스캔 데이터'와 'DB 정보'를 대조
                    if str(row[1]) == label['qr_data'] or db_name in label['qr_data']:
                        status_text = f"[OK] {db_name}"
                        color = (0, 255, 0)
                    else:
                        status_text = f"[ERR] Scan:{label['qr_data']} != DB:{db_name}"
                        color = (0, 0, 255)
                elif not label['qr_data']:
                    status_text = "[QR FAIL] Cannot Read"
                    color = (0, 255, 255) # 노란색 (인식 실패)
                else:
                    status_text = "[DB ERR] No Data"
                    color = (0, 0, 255)

                self.draw_result(frame, matched_product['bbox'], status_text, color)

            else:
                # Case 4: 바코드(라벨)는 있는데 위에 물건이 없음 (재고 부족)
                empty_msg = f"[EMPTY] {label['name']} Out of Stock"
                self.draw_result(frame, label['bbox'], empty_msg, (255, 0, 255)) # 보라색

        # 4. Case 3: 물품만 있고 매칭된 바코드가 없는 경우 (오인식 혹은 라벨 누락)
        for prod in products:
            if not prod['matched']:
                self.draw_result(frame, prod['bbox'], "[CHECK] No Label", (0, 255, 255)) # 노란색

        # 5. 최종 가공된 이미지를 전송
        res_msg = self.bridge.cv2_to_compressed_imgmsg(frame, dst_format='jpg')
        self.publisher.publish(res_msg)
    def draw_result(self, frame, bbox, text, color):
        #이미지에 사각형 박스와 상태 텍스트를 그리는 함수
        x1, y1, x2, y2 = bbox

        # 1. 객체 바운딩 박스 그리기 (선 두께 2)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # 2. 배경이 보일 수 있도록 텍스트 위치 선정 및 그리기
        # 폰트, 크기(0.5~0.6), 색상, 두께 순서
        cv2.putText(frame, text, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    def __del__(self):  # 소멸자 - ctrl+C 종료로 인한 DB 커밋 오류 방지
        if hasattr(self, 'conn'):
            self.conn.close()

def main(args=None):
    rclpy.init(args=args)
    node = VerifierNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
