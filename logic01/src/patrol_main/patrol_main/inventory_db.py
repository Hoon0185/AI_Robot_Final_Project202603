import json
import os
import requests
from datetime import datetime
from ament_index_python.packages import get_package_share_directory

class InventoryDB:
    def __init__(self, base_url="http://16.184.56.119/api"):
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
        """UI의 db_table (6개 컬럼) 형식: [카테고리, 제품명, 바코드, 기준수량, 동기화시각, 위치]"""
        try:
            res = requests.get(f"{self.base_url}/inventory", timeout=2.0)
            if res.status_code == 200:
                server_data = res.json()
                return [
                    [d.get('category', '-'), d.get('product_name', '-'), 
                     d.get('barcode', '-'), d.get('min_inventory_qty', 0), 
                     d.get('last_updated_at', 'No Data'), d.get('waypoint_name', '-')]
                    for d in server_data
                ]
        except Exception:
            pass

        return self._get_local_data("inventory", [("-", "데이터 없음", "-", 0, "-", "-")])

    def get_alarms(self):
        """UI의 alarm_table (4개 컬럼) 형식: [카테고리, 제품명, 위치, 상태]"""
        try:
            res = requests.get(f"{self.base_url}/alerts", timeout=2.0)
            if res.status_code == 200:
                server_data = res.json()
                return [
                    [d.get('category', '-'), d.get('product_name', '-'), 
                     d.get('waypoint_name', '-'), d.get('alert_type', 'X')]
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
        """서버로 바코드 인식 결과 전송 (DetectionInput 형식)"""
        payload = {
            "tag_barcode": tag_barcode,
            "detected_barcode": detected_barcode if detected_barcode else None,
            "confidence": float(confidence),
            "odom_x": 0.0,
            "odom_y": 0.0,
            "timestamp": datetime.now().isoformat()
        }
        try:
            res = requests.post(f"{self.base_url}/detections/add", json=payload, timeout=2.0)
            return res.status_code == 200, res.text
        except Exception as e:
            return False, str(e)
