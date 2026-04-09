import mysql.connector
from mysql.connector import Error

class Verifier:
    def __init__(self):
        pass

    def verify(self, qrs, items):
        if not qrs:
            return None

        # 가장 큰 QR(기준점) 찾기 로직
        best_qr = max(qrs, key=lambda x: (x.box[2] - x.box[0]) * (x.box[3] - x.box[1]))
        q_cx = (best_qr.box[0] + best_qr.box[2]) / 2
        detected_barcode = best_qr.raw_data  # .text -> .raw_data 로 변경
        qr_bbox = best_qr.box

        # 결과 상태 변수 초기화
        status = '결품'
        item_name = "물품 확인중..."
        prod_bbox = [0, 0, 0, 0]
        confidence = 0.0  # 신뢰도 변수
        class_id = -1 # 물품 미인식시 -1(Default 값)

        # 초기값 설정 (물품이 없을 경우 대비)
        matched_item = None
        min_dist = 9999

        # 3. 가장 가까운 YOLO 물품 매칭
        for item in items:
            p_cx = (item.box[0] + item.box[2]) / 2
            dist = abs(p_cx - q_cx)
            if dist < min_dist and dist < 250:
                min_dist = dist
                matched_item = item

        # 분류 작업 실행
        if matched_item:
            status = '탐지됨'
            item_name = matched_item.class_name
            prod_bbox = matched_item.box
            confidence = matched_item.score
            class_id = matched_item.class_id

        return {
            'qr_bbox': qr_bbox,
            'prod_bbox': prod_bbox,
            'detected_barcode': detected_barcode,
            'confidence': float(confidence),
            'class_id': int(class_id),
            'item_name': item_name,
            'status': status
        }
