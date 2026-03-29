import requests
import json
import time
import threading
import sys
import random
from datetime import datetime
from typing import List, Optional

# --- Configuration ---
BASE_URL = "http://localhost:8000"
DETECT_URL = f"{BASE_URL}/detections/add"
CONFIG_URL = f"{BASE_URL}/patrol/config"
PLAN_URL = f"{BASE_URL}/patrol/plan"
COMMAND_URL = f"{BASE_URL}/robot/command/latest"
COMMAND_FINISH_URL = f"{BASE_URL}/robot/command"  # /{id}/complete
START_PATROL_URL = f"{BASE_URL}/patrol/start"
FINISH_PATROL_URL = f"{BASE_URL}/patrol/finish"
STOP_PATROL_URL = f"{BASE_URL}/patrol/stop"
LIST_PRODUCTS_URL = f"{BASE_URL}/products"

# Robot Status
STATUS_IDLE = "IDLE"
STATUS_PATROLLING = "PATROLLING"
STATUS_RETURNING = "RETURNING"
STATUS_EMERGENCY_STOP = "EMERGENCY_STOP"

class VirtualRobot:
    def __init__(self):
        self.status = STATUS_IDLE
        self.avoidance_time = 5  # default
        self.patrol_path = []
        self.products = []
        self.current_patrol_id = None
        self.stop_event = threading.Event()
        self.polling_thread = None
        self.print_lock = threading.Lock()
        
    def safe_print(self, msg):
        with self.print_lock:
            print(msg)

    def print_menu(self):
        with self.print_lock:
            print("\n" + "="*50)
            print(f"🤖 Gilbot 가상 로봇 시뮬레이터 | 상태: [{self.status}]")
            print("="*50)
            print("1. [순찰 시작] (START_PATROL)")
            print("2. [비상 정지] (EMERGENCY_STOP)")
            print("3. [기지 복귀] (RETURN_TO_BASE)")
            print("4. [메모리 로드] (설정 및 경로 업데이트)")
            print("q. 종료")
            print("-" * 50)
            print("명령을 선택하세요: ", end="", flush=True)

    def load_memory(self):
        """서버에서 설정 정보 및 웨이포인트 경로를 읽어 메모리에 저장"""
        self.safe_print("\n[상태] 설정 정보 및 웨이포인트 경로 메모리 탑재 중...")
        try:
            # 1. 회피 대기 시간 로드
            conf_res = requests.get(CONFIG_URL)
            if conf_res.status_code == 200:
                self.avoidance_time = conf_res.json().get("avoidance_wait_time", 5)
                self.safe_print(f"   - 회피 대기 시간: {self.avoidance_time}초")
            
            # 2. 이동 경로 (웨이포인트 순서) 로드
            plan_res = requests.get(PLAN_URL)
            if plan_res.status_code == 200:
                self.patrol_path = plan_res.json()
                self.safe_print(f"   - 등록된 웨이포인트/상품 수: {len(self.patrol_path)}개")
                for i, p in enumerate(self.patrol_path):
                    self.safe_print(f"     [{i+1}] {p['waypoint_name']} (태그: {p['barcode_tag']} | 상품: {p['product_name']})")
            
            # 3. 전체 상품 정보 로드 (임의의 디텍션 시나리오용)
            prod_res = requests.get(LIST_PRODUCTS_URL)
            if prod_res.status_code == 200:
                self.products = prod_res.json()
                self.safe_print(f"   - 인식 가능한 상품 수: {len(self.products)}개")
                
            return True
        except Exception as e:
            self.safe_print(f"❌ 데이터 로딩 실패: {e}")
            return False

    def send_detection(self, tag_barcode, detected_barcode, confidence=0.98):
        payload = {
            "tag_barcode": tag_barcode,
            "detected_barcode": detected_barcode,
            "confidence": confidence,
            "odom_x": 1.23, # 시뮬레이션 가상 좌표
            "odom_y": 4.56,
            "timestamp": datetime.now().isoformat()
        }
        try:
            res = requests.post(DETECT_URL, json=payload)
            if res.status_code == 200:
                data = res.json()
                self.current_patrol_id = data.get("patrol_id")
                self.safe_print(f"   >>> [인식 결과] 태그:{tag_barcode} | 상품:{detected_barcode if detected_barcode else 'NO_ITEM'} -> {data.get('judgment')}")
            else:
                self.safe_print(f"   >>> ❌ 서버 응답 오류: {res.status_code}")
        except Exception as e:
            self.safe_print(f"   >>> ❌ 전송 중 오류: {e}")

    def start_patrol(self, remote=False):
        if self.status == STATUS_PATROLLING:
            self.safe_print("⚠️ 이미 순찰 중입니다.")
            return

        self.safe_print("\n" + "="*40)
        self.safe_print("🚀 [순찰 개시] 로봇이 순찰을 시작합니다.")
        self.safe_print("="*40)
        
        # 순찰 개시 전 데이터 로딩
        if not self.load_memory():
            self.safe_print("❌ 순찰을 시작할 수 없습니다. (메모리 탑재 실패)")
            return

        if not remote:
            # 직접 시작하는 경우 서버에 신호 전송
            try:
                res = requests.post(START_PATROL_URL)
                if res.status_code == 200:
                    self.current_patrol_id = res.json().get("patrol_id")
                    self.safe_print(f"✅ 서버에 순찰 시작 신호를 보냈습니다. (Patrol ID: {self.current_patrol_id})")
                else:
                    self.safe_print("⚠️ 서버 신호 전송 실패 (직접 진행)")
            except:
                self.safe_print("⚠️ 서버 연결 실패 (오프라인 시뮬레이션)")

        self.status = STATUS_PATROLLING
        
        # 순찰 시나리오 시뮬레이션
        for i, plan in enumerate(self.patrol_path):
            if self.status != STATUS_PATROLLING:
                self.safe_print("🛑 순찰이 중단되었습니다.")
                if remote: self.print_menu()
                return

            self.safe_print(f"\n[{i+1}/{len(self.patrol_path)}] {plan['waypoint_name']} 이동 중...")
            time.sleep(2) # 이동 시간 시뮬레이션
            
            self.safe_print(f"📍 {plan['waypoint_name']} 도착. 스캔 중...")
            time.sleep(1) # 스캔 시간 시뮬레이션
            
            # 실제 스캔 시뮬레이션 (90% 확률로 정상, 5% 확률로 결품, 5% 확률로 오진열)
            rand_val = random.random()
            
            if rand_val < 0.8:
                # 정상
                self.send_detection(plan['barcode_tag'], plan['product_barcode'])
            elif rand_val < 0.9:
                # 결품
                self.send_detection(plan['barcode_tag'], None, 0.0)
            else:
                # 오진열 (다른 무작위 상품 선택)
                other_products = [p for p in self.products if p['barcode'] != plan['product_barcode']]
                if other_products:
                    other_p = random.choice(other_products)
                    self.send_detection(plan['barcode_tag'], other_p['barcode'], 0.95)
                else:
                    self.send_detection(plan['barcode_tag'], "0000000000000", 0.5)

            # 회피 대기 시간 적용 (마지막 웨이포인트 제외이며, 장애물 감지 시에만 발생)
            if i < len(self.patrol_path) - 1:
                # 30% 확률로 사람이 매대 앞을 막고 있는 시나리오 시뮬레이션
                if random.random() < 0.3:
                    self.safe_print(f"⚠️ [장애물 감지] 매대 앞에 고객이 있습니다. {self.avoidance_time}초 대기 후 이동합니다...")
                    time.sleep(self.avoidance_time)
                else:
                    self.safe_print("⏭️ 장애물 없음. 다음 위치로 즉시 이동합니다.")

        self.safe_print("\n✅ 모든 웨이포인트 순찰 완료.")
        self.return_to_base(remote=remote)

    def return_to_base(self, remote=False):
        self.safe_print("\n🏠 [기지 복귀] 기지로 복귀합니다...")
        self.status = STATUS_RETURNING
        time.sleep(3) # 복귀 이동 시간 시뮬레이션
        
        self.safe_print("🏁 [복귀 완료] 로봇이 기지에 도착했습니다.")
        self.status = STATUS_IDLE
        
        # 복귀 완료 신호 전송
        if not remote:
            try:
                res = requests.post(FINISH_PATROL_URL)
                if res.status_code == 200:
                    self.safe_print("✅ 서버에 기지 복귀 완료 신호를 전송했습니다.")
            except:
                pass
        
        # 원격 실행인 경우 메뉴 재출력
        if remote:
            self.print_menu()

    def emergency_stop(self, remote=False):
        self.safe_print("\n🚨 [비상 정지] 로봇 동작이 강제 중단되었습니다!")
        self.status = STATUS_EMERGENCY_STOP
        
        if not remote:
            try:
                requests.post(STOP_PATROL_URL)
                self.safe_print("✅ 서버에 비상 정지 신호를 전송했습니다.")
            except:
                pass
        
        # 원격 실행인 경우 메뉴 재출력
        if remote:
            self.print_menu()

    def poll_commands(self):
        """서버로부터 원격 명령을 주기적으로 확인 (Light 서버 신호 수신 역할)"""
        while not self.stop_event.is_set():
            try:
                res = requests.get(COMMAND_URL)
                if res.status_code == 200:
                    cmd_data = res.json()
                    cmd_type = cmd_data.get("command_type")
                    cmd_id = cmd_data.get("command_id")
                    
                    if cmd_type and cmd_type != "IDLE":
                        self.safe_print(f"\n📡 [원격 신호 수신] {cmd_type} (ID: {cmd_id})")
                        
                        if cmd_type == "START_PATROL":
                            threading.Thread(target=self.start_patrol, args=(True,)).start()
                        elif cmd_type == "RETURN_TO_BASE":
                            threading.Thread(target=self.return_to_base, args=(True,)).start()
                        elif cmd_type == "EMERGENCY_STOP":
                            self.emergency_stop(remote=True)
                        
                        # 명령 완료 처리 알림
                        if cmd_id:
                            requests.post(f"{BASE_URL}/robot/command/{cmd_id}/complete")
                            
            except Exception as e:
                pass
            
            time.sleep(2) # 2초마다 확인

    def run(self):
        # 원격 명령 수신 스레드 시작
        self.polling_thread = threading.Thread(target=self.poll_commands, daemon=True)
        self.polling_thread.start()
        
        self.safe_print("="*50)
        self.safe_print("🤖 Gilbot 확장 가상 로봇 시뮬레이터 v2.1")
        self.safe_print("   - 서버 주소: " + BASE_URL)
        self.safe_print("   - 상태: 원격 신호 대기 중 (Polling)")
        self.safe_print("="*50)
        
        while True:
            self.print_menu()
            choice = sys.stdin.readline().strip().lower()
            
            if not choice: # 엔터만 친 경우 메뉴 재출력
                continue
                
            if choice == '1':
                self.start_patrol()
            elif choice == '2':
                self.emergency_stop()
            elif choice == '3':
                self.return_to_base()
            elif choice == '4':
                self.load_memory()
            elif choice == 'q':
                self.safe_print("시뮬레이터를 종료합니다.")
                self.stop_event.set()
                break
            else:
                self.safe_print("❌ 잘못된 선택입니다.")

if __name__ == "__main__":
    robot = VirtualRobot()
    robot.run()
