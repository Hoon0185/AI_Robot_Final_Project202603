import mysql.connector
from mysql.connector import Error

class Verifier:
    def __init__(self):
        # 1. DB 설정 정보 (직접 입력하거나 환경변수에서 로드)
        self.db_config = {
            'host': '16.184.56.119',
            'user': 'gilbot',
            'password': 'robot123',
            'database': 'gilbot',
            'port': 3306  # 기본 포트
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
        # 1. 바코드와 상품이 모두 없으면 분석 불가
        if not qrs and not items:
            return None

        # 연결 상태 확인 및 재연결
        if not self.conn or not self.conn.is_connected():
            self._connect_db()
            if not self.conn: return None

        # 바코드와 상품 탐지 개수 확인
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

        # 3. MySQL 실행 (바코드가 발견되면 실물 바코드로, 없으면 로봇이 준 목표 바코드로 조회)
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

        # 결과 상태 변수 초기화
        status = '결품'
        item_name = "물품 확인중..."
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

        # 5. 최종 검증 상태 결정
        if row:
            db_product_name, db_yolo_id = row
            if matched_item:
                bbox = matched_item['bbox']
                current_yolo_id = matched_item['id']
                detected_yolo_id = current_yolo_id
                confidence = matched_item['score']

                # YOLO ID 비교 (디버깅 로그 포함)
                if int(current_yolo_id) == int(db_yolo_id):
                    status = '정상'
                    if not best_qr:
                        item_name = f"[상품판독 성공] {db_product_name}"
                    else:
                        item_name = db_product_name
                else:
                    print(f"⚠️ [ID 불일치] DB ID: {db_yolo_id} | 인식 ID: {current_yolo_id} ({db_product_name})")
                    if not best_qr:
                        status = 'QR_MISSING' # 바코드가 없으므로 오배열 대신 MISSING으로 보고 (로봇의 재시도 유도)
                        item_name = f"상품 불일치 (기대: {db_product_name})"
                    else:
                        status = '오배열'
                        item_name = db_product_name
            else:
                status = '결품'
                item_name = db_product_name
        elif not best_qr and matched_item:
            # 바코드도 없고 DB 조회도 실패했지만 상품은 있는 경우
            status = 'QR_MISSING'
            item_name = f"미확인 상품 (ID: {matched_item['id']})"
            bbox = matched_item['bbox']
            detected_yolo_id = matched_item['id']
            confidence = matched_item['score']
        else:
            status = '오배열'
            item_name = "분석 불가(QR/상품 없음)"

        return {
            'item_name': item_name,
            'status': status,
            'barcode': detected_barcode,
            'bbox': bbox,
            'confidence': float(confidence),
            'yolo_id': int(detected_yolo_id)
        }
