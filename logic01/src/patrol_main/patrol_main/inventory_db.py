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

    def get_patrol_history(self):
        """서버에서 최근 10개의 순찰 이력 조회"""
        try:
            res = requests.get(f"{self.base_url}/patrol/list", timeout=2.0)
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass
        return []

    def get_patrol_config(self):
        """서버에서 현재 순찰 설정 조회"""
        try:
            res = requests.get(f"{self.base_url}/patrol/config", timeout=2.0)
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass
        return None

    def update_patrol_config(self, avoidance_wait=10, start="09:00", end="22:00", hour=0, minute=0):
        """서버로 새로운 순찰 설정 전송 (시/분 분리 전송)"""
        # ... (생략)
        payload = {
            "avoidance_wait_time": int(avoidance_wait),
            "patrol_start_time": start,
            "patrol_end_time": end,
            "interval_hour": int(hour),
            "interval_minute": int(minute),
            "is_active": True
        }
        try:
            res = requests.post(f"{self.base_url}/patrol/config", json=payload, timeout=2.0)
            return res.status_code == 200
        except Exception:
            return False

    def get_latest_command(self):
        """서버 대시보드에서 보낸 최신 원격 명령을 가져옵니다."""
        try:
            res = requests.get(f"{self.base_url}/robot/command/latest", timeout=1.0)
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass
        return None

    def get_waypoints(self):
        """서버에서 모든 웨이포인트 목록을 가져옵니다."""
        try:
            res = requests.get(f"{self.base_url}/waypoints", timeout=2.0)
            if res.status_code == 200:
                data = res.json()
                # 로봇 노드에서 사용하는 'shelves' 형식으로 변환
                waypoints = {}
                for wp in data:
                    name = wp.get('waypoint_name', 'unknown')
                    waypoints[name] = {
                        'x': float(wp.get('loc_x', 0.0)),
                        'y': float(wp.get('loc_y', 0.0)),
                        'yaw': float(wp.get('loc_yaw', 0.0)),
                        'tag_barcode': name  # 사용자의 요청대로 waypoint_name을 tag_barcode로 사용
                    }
                return waypoints
        except Exception as e:
            print(f"[DB] Failed to fetch waypoints: {e}")
        return None
