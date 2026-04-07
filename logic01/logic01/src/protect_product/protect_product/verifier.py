import sqlite3

class Verifier:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def verify(self, qr_list, yolo_list):
        if not qr_list:
            return None

        # 가장 큰 QR(기준점) 찾기
        best_qr = max(qr_list, key=lambda x: (x['bbox'][2]-x['bbox'][0])*(x['bbox'][3]-x['bbox'][1]))
        q_cx = (best_qr['bbox'][0] + best_qr['bbox'][2]) / 2
        detected_barcode = best_qr['text'] # 인식된 바코드 문자열
        self.cursor.execute("SELECT product_name, yolo_class_id FROM product_master WHERE barcode=?", (detected_barcode,))
        row = self.cursor.fetchone()

        # 결과 상태 변수 초기화
        status = '결품' # 기본값을 결품으로 설정
        item_name = "물품 확인중..."
        bbox = [0, 0, 0, 0]

        # 가장 가까운 YOLO 물품과 QR 매칭, 일정 거리 이상 차이날 경우 정상 배치가 아닌것으로 판정
        matched_item = None
        min_dist = 9999
        for item in yolo_list:
            p_cx = (item['bbox'][0] + item['bbox'][2]) / 2
            dist = abs(p_cx - q_cx)
            if dist < min_dist and dist < 250:# 250픽셀 이내로 매칭이 안된다면
                min_dist = dist
                matched_item = item

        # 검증 작업 실행
        if row:
            # DB에 등록된 바코드인 경우
            db_product_name = row[0]
            db_yolo_id = row[1]

            if matched_item:
                bbox = matched_item['bbox']
                current_yolo_id = matched_item['id']
                # YOLO가 인식한 ID와 DB에 등록된 해당 바코드의 YOLO ID가 일치하는지 확인
                if current_yolo_id == db_yolo_id:
                    status = '정상'
                    item_name = db_product_name
                else:
                    status = '오배열'
                    item_name = db_product_name
                    # f"실제:{matched_item['name']} (기대:{db_product_name})"
            else:
                status = '결품'
                item_name = db_product_name
        else:
            # DB에 없는 바코드인 경우 (미등록 상품 태그)
            status = '오배열'
            item_name = "미등록 바코드"

        return {
            'item_name': item_name,
            'status': status,
            'barcode': detected_barcode,
            'bbox': bbox
        }
