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

    def verify(self, qrs, items):
        if not qrs:
            return None

        # 연결 상태 확인 및 재연결
        if not self.conn or not self.conn.is_connected():
            self._connect_db()
            if not self.conn: return None

        # 가장 큰 QR(기준점) 찾기 로직 (기존과 동일)
        best_qr = max(qrs, key=lambda x: (x['bbox'][2]-x['bbox'][0])*(x['bbox'][3]-x['bbox'][1]))
        q_cx = (best_qr['bbox'][0] + best_qr['bbox'][2]) / 2
        detected_barcode = best_qr['text']

        # 2. MySQL 실행
        cursor = self.conn.cursor()
        try: # (파라미터 문법 변경: ? -> %s)
            query = "SELECT product_name, yolo_class_id FROM product_master WHERE barcode = %s"
            cursor.execute(query, (detected_barcode,))
            row = cursor.fetchone()
        except Error as e:
            print(f"Query Error: {e}")
            row = None
        finally:
            cursor.close()

        # 결과 상태 변수 초기화
        status = '결품'
        item_name = "물품 확인중..."
        bbox = [0, 0, 0, 0]
        confidence = 0.0  # 신뢰도 변수
        detected_yolo_id = -1 # 클래스 ID

        # 가장 가까운 YOLO 물품 매칭 (기존 로직 유지)
        matched_item = None
        min_dist = 9999
        for item in items:
            p_cx = (item['bbox'][0] + item['bbox'][2]) / 2
            dist = abs(p_cx - q_cx)
            if dist < min_dist and dist < 250:
                min_dist = dist
                matched_item = item

        # 3. 검증 작업 실행
        if row:
            db_product_name, db_yolo_id = row # 튜플 언패킹

            if matched_item:
                bbox = matched_item['bbox']
                current_yolo_id = matched_item['id']

                # YOLO ID 비교
                if int(current_yolo_id) == int(db_yolo_id): # 타입 일치 확인
                    status = '정상'
                else:
                    status = '오배열'
                item_name = db_product_name
            else:
                status = '결품'
                item_name = db_product_name
        else:
            status = '오배열'
            item_name = "미등록 바코드"

        return {
            'item_name': item_name,
            'status': status,
            'barcode': detected_barcode,
            'bbox': bbox,
            'confidence': float(confidence),
            'yolo_id': int(detected_yolo_id)
        }
