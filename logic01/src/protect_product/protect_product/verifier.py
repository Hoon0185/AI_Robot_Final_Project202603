import mysql.connector
from mysql.connector import Error

class Verifier:
    def __init__(self):
        # 1. DB 설정 정보
        self.db_config = {
            'host': '16.184.56.119',
            'user': 'gilbot',
            'password': 'robot123',
            'database': 'gilbot',
            'port': 3306 
        }
        self.conn = None
        self._connect_db()

    def _connect_db(self):
        """데이터베이스 재연결 로직"""
        try:
            if self.conn:
                self.conn.close()
            self.conn = mysql.connector.connect(**self.db_config)
            print("✅ Remote MySQL Database connected")
        except Error as e:
            print(f"❌ Database Connection Error: {e}")
            self.conn = None

    def verify(self, qrs, items, target_barcode="UNKNOWN"):
        # 1. 데이터가 아예 없으면 '결품'으로 즉각 판단 (사용자 요청 반영)
        if not qrs and not items:
            return {
                'item_name': "인식 불가 (결품)",
                'status': '결품',
                'barcode': "NONE",
                'bbox': [0, 0, 0, 0],
                'confidence': 0.0,
                'yolo_id': -1
            }

        # 연결 상태 확인 및 재연결
        if not self.conn or not self.conn.is_connected():
            self._connect_db()
            if not self.conn: return None

        num_qrs = len(qrs)
        num_items = len(items)

        # 2. 기준점 및 바코드 설정
        best_qr = None
        q_cx = -1
        detected_barcode = "QR_NOT_FOUND"

        if num_qrs > 0:
            best_qr = max(qrs, key=lambda x: (x['bbox'][2]-x['bbox'][0])*(x['bbox'][3]-x['bbox'][1]))
            q_cx = (best_qr['bbox'][0] + best_qr['bbox'][2]) / 2
            detected_barcode = best_qr['text']

        # 3. MySQL 실행 (바코드 우선, 없으면 로봇의 목표 바코드로 정보 조회)
        row = None
        search_barcode = detected_barcode if best_qr else target_barcode
        
        if search_barcode != "QR_NOT_FOUND" and search_barcode != "UNKNOWN":
            cursor = self.conn.cursor()
            try:
                query = "SELECT product_name, yolo_class_id FROM product_master WHERE barcode = %s"
                cursor.execute(query, (search_barcode,))
                row = cursor.fetchone()
            except Error as e:
                print(f"Query Error: {e}")
            finally:
                cursor.close()

        # 결과 변수 초기화 (기본값: 결품)
        status = '결품'
        item_name = "미인식 (결품)"
        bbox = [0, 0, 0, 0]
        confidence = 0.0
        detected_yolo_id = -1

        # 4. 상품 매칭 시도
        matched_item = None
        if num_items > 0:
            if best_qr:
                # 바코드가 있다면 가장 가까운 상품 매칭
                min_dist = 9999
                for item in items:
                    p_cx = (item['bbox'][0] + item['bbox'][2]) / 2
                    dist = abs(p_cx - q_cx)
                    if dist < min_dist and dist < 250:
                        min_dist = dist
                        matched_item = item
            else:
                # 바코드가 없다면 가장 신뢰도 높은 상품 선택
                matched_item = max(items, key=lambda x: x['score'])

        # 5. 최종 검증 상태 결정 (웹/DB 정합성 기준)
        if row:
            db_product_name, db_yolo_id = row
            if matched_item:
                bbox = matched_item['bbox']
                current_yolo_id = matched_item['id']
                detected_yolo_id = current_yolo_id
                confidence = matched_item['score']

                # 정합성 판단 (DB의 yolo_class_id를 절대 진리로 따름)
                if int(current_yolo_id) == int(db_yolo_id):
                    status = '정상'
                    item_name = db_product_name if best_qr else f"[상품판독 성공] {db_product_name}"
                else:
                    # 정보가 다르면 무조건 '오진열'
                    status = '오진열'
                    print(f"⚠️ [ID 불일치] DB ID: {db_yolo_id} | 인식 ID: {current_yolo_id} ({db_product_name})")
                    item_name = f"상품 불일치 (기대: {db_product_name})"
            else:
                # 기대 상품 위치에 상품이 없으면 '결품'
                status = '결품'
                item_name = f"{db_product_name} (결품)"
        elif not best_qr and matched_item:
            # 바코드는 없고 엉뚱한(?) 상품만 있는 경우 -> 오진열로 통일
            status = '오진열'
            item_name = f"미등록 상품 (ID: {matched_item['id']})"
            bbox = matched_item['bbox']
            detected_yolo_id = matched_item['id']
            confidence = matched_item['score']
        else:
            # 최종적으로 탐지된 것이 아무것도 없을 때
            status = '결품'
            item_name = "인식 불가 (결품)"

        return {
            'item_name': item_name,
            'status': status,
            'barcode': detected_barcode,
            'bbox': bbox,
            'confidence': float(confidence),
            'yolo_id': int(detected_yolo_id)
        }
