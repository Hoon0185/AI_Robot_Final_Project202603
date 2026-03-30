import json
import os
import requests
from ament_index_python.packages import get_package_share_directory

class InventoryDB:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        try:
            pkg_dir = get_package_share_directory('patrol_main')
            self.json_path = os.path.join(pkg_dir, 'resource', 'inventory.json')
            if not os.path.exists(self.json_path):
                # Fallback to src directory for development/testing
                current_dir = os.path.dirname(os.path.abspath(__file__))
                self.json_path = os.path.join(current_dir, '..', 'resource', 'inventory.json')
        except Exception:
            self.json_path = 'inventory.json'

    def get_inventory(self):
        """UI의 db_table (6개 컬럼) 형식에 맞는 목록 반환: [카테고리, 제품명, 바코드, 기준수량, 동기화시각, 위치]"""
        # 1. 서버 연동 시도
        try:
            res = requests.get(f"{self.base_url}/v1/ui/inventory", timeout=2.0)
            if res.status_code == 200:
                server_data = res.json()
                # 서버 데이터를 UI 형식으로 변환 (서버 데이터 구조에 따라 매핑 필요)
                # 예시: [{"category": "과자", "name": "포카칩", "barcode": "...", "std_qty": 10, "last_sync": "...", "location": "..."}]
                return [
                    [d.get('category', '-'), d.get('name', d.get('product_name', '-')), 
                     d.get('barcode', '-'), d.get('std_qty', d.get('standard_quantity', 0)), 
                     d.get('last_sync', d.get('updated_at', 'No Data')), d.get('location', d.get('waypoint_id', '-'))]
                    for d in server_data
                ]
        except Exception:
            pass # 서버 연결 실패 시 로컬 데이터 사용

        # 2. 로컬 JSON 데이터 반환
        return self._get_local_data("inventory", [("-", "데이터 없음", "-", 0, "-", "-")])

    def get_alarms(self):
        """UI의 alarm_table (4개 컬럼) 형식에 맞는 목록 반환: [카테고리, 제품명, 위치, 상태]"""
        try:
            res = requests.get(f"{self.base_url}/v1/ui/alerts", timeout=2.0)
            if res.status_code == 200:
                server_data = res.json()
                return [
                    [d.get('category', '-'), d.get('name', d.get('product_name', '-')), 
                     d.get('location', d.get('shelf_id', '-')), d.get('status', d.get('alert_type', 'X'))]
                    for d in server_data
                ]
        except Exception:
            pass

        return self._get_local_data("alarms", [("-", "알림 없음", "-", "O")])

    def _get_local_data(self, key, default):
        if not os.path.exists(self.json_path):
            return default
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get(key, default)
        except Exception:
            return default

    def report_detection(self, tag_barcode, detected_barcode, confidence=0.99):
        """서버로 바코드 인식 결과 전송"""
        payload = {
            "tag_barcode": tag_barcode,
            "detected_barcode": detected_barcode,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }
        try:
            res = requests.post(f"{self.base_url}/v1/robot/inventory", json=payload, timeout=2.0)
            return res.status_code == 200, res.text
        except Exception as e:
            return False, str(e)
