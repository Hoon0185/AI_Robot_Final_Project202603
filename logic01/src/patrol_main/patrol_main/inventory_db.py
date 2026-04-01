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
        """서버 대시보드에서 보낸 최신 원격 명령을 가져옵니다. (id 포함)"""
        try:
            res = requests.get(f"{self.base_url}/robot/command/latest", timeout=1.0)
            if res.status_code == 200:
                data = res.json()
                # command_type 또는 command 필드 추출
                cmd_type = data.get('command_type') or data.get('command')
                if cmd_type and cmd_type != "IDLE":
                    return data
        except Exception:
            pass
        return None

    def complete_command(self, command_id):
        """명령 수행이 완료되었음을 서버에 알립니다."""
        try:
            res = requests.post(f"{self.base_url}/robot/command/{command_id}/complete", timeout=2.0)
            return res.status_code == 200
        except Exception:
            return False

    def start_patrol_session(self):
        """서버에 순찰 시작 세션을 생성하고 patrol_id를 반환합니다."""
        try:
            res = requests.post(f"{self.base_url}/patrol/start", timeout=2.0)
            if res.status_code == 200:
                return res.json().get('patrol_id')
        except Exception:
            pass
        return None

    def finish_patrol_session(self):
        """진행 중인 순찰 세션을 완료 상태로 변경합니다."""
        try:
            res = requests.post(f"{self.base_url}/patrol/finish", timeout=2.0)
            return res.status_code == 200
        except Exception:
            return False

    def get_waypoints(self):
        """서버에서 모든 웨이포인트 목록을 가져옵니다. (단순 목록)"""
        # ... (이전과 동일)
        try:
            res = requests.get(f"{self.base_url}/waypoints", timeout=2.0)
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass
        return None

    def get_active_patrol_plan(self):
        """서버의 '순찰 계획 및 시퀀스'에 따른 정렬된 좌표 리스트를 가져옵니다."""
        try:
            # 1. 모든 웨이포인트의 좌표 정보 가져오기
            w_res = requests.get(f"{self.base_url}/waypoints", timeout=2.0)
            if w_res.status_code != 200: return None
            waypoints_db = {wp['waypoint_id']: wp for wp in w_res.json()}

            # 2. 순찰 계획(Sequence) 가져오기
            p_res = requests.get(f"{self.base_url}/patrol/plan", timeout=2.0)
            if p_res.status_code != 200: return None
            plan_data = p_res.json()

            # 3. 계획된 순서대로 좌표 매칭
            active_plan = {}
            for item in plan_data:
                wp_id = item['waypoint_id']
                if wp_id in waypoints_db:
                    wp_info = waypoints_db[wp_id]
                    # 'shelf_1' 같은 이름 대신 'TAG-A1-001' 같은 바코드 태그를 키로 사용하거나,
                    # 순찰 시퀀스 내의 유니크한 이름을 키로 사용
                    name = item.get('waypoint_name') or f"plan_{item['plan_id']}"
                    active_plan[name] = {
                        'x': float(wp_info.get('loc_x', 0.0)),
                        'y': float(wp_info.get('loc_y', 0.0)),
                        'yaw': float(wp_info.get('loc_yaw', 0.0)),
                        'tag_barcode': item.get('barcode_tag') or name
                    }
            return active_plan
        except Exception as e:
            print(f"[DB] Error fetching patrol plan: {e}")
        return None
    def report_robot_pose(self, x, y, status="IDLE"):
        """서버로 로봇의 현재 실시간 좌표 및 상태 전송 (odom_x, odom_y, status)"""
        payload = {
            "odom_x": float(x),
            "odom_y": float(y),
            "status": str(status) # IDLE, PATROLLING, WAITING, RETURNING, EMERGENCY 등
        }
        try:
            res = requests.post(f"{self.base_url}/robot/pose", json=payload, timeout=1.0)
            return res.status_code == 200
        except Exception:
            return False
