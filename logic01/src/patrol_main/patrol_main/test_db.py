import os
import json
from datetime import datetime

class InventoryDB:
    def __init__(self, base_url="http://16.0.0.0"):
        self.base_url = base_url
        # 1. 초기화 안내 출력
        print("\n" + "="*50)
        print("[OFFLINE MODE] InventoryDB가 더미 모드로 시작되었습니다.")
        print(f"[STATUS] 서버 연결 시도 안 함 (Target: {self.base_url})")
        print("="*50 + "\n")

    # --- 1. 재고 및 데이터 조회 관련 ---
    def get_inventory(self):
        """재고 현황 조회"""
        return [["분류", "더미상품", "DUMMY-001", 10, "2026-04-08", "A-1"]]

    def get_alarms(self):
        """알람 내역 조회"""
        return [["-", "알림 없음", "-", "O"]]

    def get_patrol_history(self):
        """순찰 이력 조회 (최근 10개)"""
        return []

    # --- 2. 로봇 상태 및 위치 보고 (매개변수 일치화) ---
    def report_robot_pose(self, x, y, status=None):
        """실시간 좌표 및 상태 업데이트"""
        return True

    def report_battery(self, percentage):
        """배터리 잔량 전송"""
        return True

    # --- 3. 인식 결과 및 AI 관련 ---
    def report_detection(self, product_name, quantity, confidence=0.99, yolo_class_id=None, tag_barcode=None):
        """AI 인식 결과 및 바코드 전송"""
        return True, "Dummy Success"

    def report_detection_result(self, session_id, detection_data):
        """인식 결과 상세 리포트 전송"""
        return True

    # --- 4. 순찰 세션 및 제어 관련 ---
    def start_patrol_session(self):
        """순찰 시작 (가짜 세션 ID 반환)"""
        return 999

    def finish_patrol_session(self):
        """순찰 완료 처리"""
        return True

    def pause_patrol_session(self, patrol_id):
        """순찰 일시 정지 보고"""
        return True

    def resume_patrol_session(self, patrol_id):
        """순찰 재개 보고"""
        return True

    # --- 5. 서버 설정 및 명령 관련 ---
    def get_patrol_config(self):
        """순찰 설정(대기시간 등) 조회"""
        # 설정이 없음을 의미하는 False 반환 (노드가 기본값을 쓰도록 유도)
        return False

    def update_patrol_config(self, **kwargs):
        """순찰 설정 변경"""
        return True

    def get_latest_command(self):
        """원격 명령(긴급정지 등) 조회"""
        return None

    def complete_command(self, command_id):
        """원격 명령 수행 완료 보고"""
        return True

    # --- 6. 기타 보조 함수 ---
    def get_robot_status(self):
        """로봇의 전반적인 상태 조회"""
        return {"status": "idle", "last_update": datetime.now().isoformat()}
