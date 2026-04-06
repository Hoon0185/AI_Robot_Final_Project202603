import json
import os
import requests
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from ament_index_python.packages import get_package_share_directory

class InventoryDB:
  def __init__(self, base_url="http://16.000000"):
      self.base_url = base_url
      try:
          pkg_dir = get_package_share_directory('patrol_main')
          self.json_path = os.path.join(pkg_dir, 'resource', 'inventory.json')
          if not os.path.exists(self.json_path):
              current_dir = os.path.dirname(os.path.abspath(__file__))
              self.json_path = os.path.join(current_dir, '..', 'resource', 'inventory.json')
      except Exception:
          self.json_path = 'inventory.json'

  def get_inventory(self):
      """UI의 db_table 형식: 로컬 파일 데이터만 즉시 반환"""
      # === 수정: 서버 요청을 차단하고 즉시 로컬 데이터를 가져옵니다 ===
      return self._get_local_data("inventory", [("-", "데이터 없음", "-", 0, "-", "-")])

  def get_alarms(self):
      """UI의 alarm_table 형식: 로컬 파일 데이터만 즉시 반환"""
      # === 수정: 서버 요청을 차단하고 즉시 로컬 데이터를 가져옵니다 ===
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

  def report_detection(self, tag_barcode, patrol_id, waypoint_id, x=None, y=None, detected_barcode=None, confidence=0.99, yolo_class_id=None):
    """서버로 인식 결과 전송 차단"""
    return True, "Local mode active"

  def get_patrol_history(self):
      """서버에서 최근 10개의 순찰 이력 조회 차단"""
      # === 수정: 빈 리스트를 즉시 반환합니다 ===
      return []

  def get_patrol_config(self):
      """서버에서 현재 순찰 설정 조회 차단"""
      # === 수정: 설정 없음(None)을 즉시 반환합니다 ===
      return None

  def update_patrol_config(self, avoidance_wait=10, start="09:00", end="22:00", hour=0, minute=0):
      """서버로 새로운 순찰 설정 전송 차단"""
      # === 수정: 전송 실패(False)로 처리하거나 True로 속입니다 ===
      return True

  def get_latest_command(self):
      """서버 대시보드에서 보낸 최신 원격 명령 조회 차단"""
      # === 수정: 명령 없음(None)을 즉시 반환합니다 ===
      return None

  def complete_command(self, command_id):
      """명령 수행 완료 알림 차단"""
      return True

  def start_patrol_session(self):
      """서버에 순찰 시작 세션 생성 차단"""
      # === 수정: 가짜 세션 ID(999)를 부여합니다 ===
      return 999

  def finish_patrol_session(self):
      """진행 중인 순찰 세션 완료 처리 차단"""
      return True

  def get_waypoints(self):
      """서버에서 모든 웨이포인트 목록 가져오기 차단"""
      return None

  def get_active_patrol_plan(self):
      """서버의 순찰 계획 및 시퀀스 가져오기 차단"""
      # === 수정: None을 반환하여 로컬 순찰 노드가 하드코딩된 기본 좌표를 쓰게 유도합니다 ===
      return None

  def report_robot_pose(self, x, y, status="IDLE"):
      """로봇 좌표 전송 차단"""
      # === 수정: 아무것도 하지 않고 성공 반환 ===
      return True

  def report_robot_pose_direct(self, x, y):
      """DB에 직접 접속하여 실시간 좌표 업데이트 차단"""
      # === 수정: 데이터베이스 접속 시도를 원천 차단합니다 ===
      return False
