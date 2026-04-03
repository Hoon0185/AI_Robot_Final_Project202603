import requests
import json
import time
import threading
import sys
import random
import logging
from datetime import datetime
from typing import List, Optional

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("robot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Gilbot")

# --- Configuration ---
LOCAL_URL = "http://localhost:8000/api"
SERVER_URL = "http://16.184.56.119/api"

if len(sys.argv) > 1:
    arg = sys.argv[1].lower()
    if arg == "local":
        BASE_URL = LOCAL_URL
    elif arg == "server":
        BASE_URL = SERVER_URL
    elif arg.startswith("http"):
        BASE_URL = arg
    else:
        # If it's not a keyword or URL, assume it's an IP or hostname
        BASE_URL = f"http://{arg}:8000/api"
else:
    BASE_URL = LOCAL_URL

DETECT_URL = f"{BASE_URL}/detections/add"
CONFIG_URL = f"{BASE_URL}/patrol/config"
PLAN_URL = f"{BASE_URL}/patrol/plan"
COMMAND_URL = f"{BASE_URL}/robot/command/latest"
COMMAND_FINISH_URL = f"{BASE_URL}/robot/command"  # /{id}/complete
START_PATROL_URL = f"{BASE_URL}/patrol/start"
FINISH_PATROL_URL = f"{BASE_URL}/patrol/finish"
STOP_PATROL_URL = f"{BASE_URL}/patrol/stop"
LIST_PRODUCTS_URL = f"{BASE_URL}/products"
CLEAR_COMMAND_URL = f"{BASE_URL}/robot/command/clear_pending"
POSE_URL = f"{BASE_URL}/robot/pose"

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
        self.status = STATUS_IDLE
        self.stop_event = threading.Event()
        self.last_index = 0 # 마지막으로 완료한 웨이포인트 인덱스
        self.current_pos = (0.0, 0.0)
        self.print_lock = threading.Lock()
        
        # 하트비트(Pose) 전용 스레드 시작
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
    def safe_print(self, msg):
        with self.print_lock:
            logger.info(msg)

    def _heartbeat_loop(self):
        """유휴 상태에서도 2초마다 서버에 위치(하트비트) 보고"""
        while not self.stop_event.is_set():
            try:
                # 현재 위치 보고 (하트비트 역할)
                self.send_pose(self.current_pos[0], self.current_pos[1])
            except Exception:
                pass
            time.sleep(2.0)

    def print_menu(self):
        with self.print_lock:
            print("\n" + "="*50)
            print(f"🤖 Gilbot 가상 로봇 시뮬레이터 | 상태: [{self.status}]")
            print("="*50)
            print("1. [순찰 시작] (START_PATROL)")
            print("2. [비상 정지] (EMERGENCY_STOP)")
            print("3. [비상 해제/재개] (RESUME_PATROL)")
            print("4. [기지 복귀] (RETURN_TO_BASE)")
            print("5. [메모리 로드] (load_memory)")
            print("q. 종료")
            print("-" * 50)
            print("명령을 선택하세요: ", end="", flush=True)


    def interruptible_sleep(self, seconds):
        """status가 바뀌면 즉시 중단되는 가변 수면 함수"""
        step = 0.5
        slept = 0
        while slept < seconds:
            if self.status == STATUS_EMERGENCY_STOP:
                return False
            time.sleep(min(step, seconds - slept))
            slept += step
        return True

    def load_memory(self):
        """서버에서 설정 정보 및 웨이포인트 경로를 읽어 메모리에 저장 (재시도 로직 포함)"""
        max_retries = 3
        retry_delay = 3
        
        logger.info("======= 데이터 로딩 시퀀스 시작 =======")

        def fetch_with_retry(url, name):
            for i in range(max_retries):
                try:
                    logger.info(f"📡 {name} 요청 중... (시도 {i+1}/{max_retries})")
                    res = requests.get(url, timeout=5)
                    if res.status_code == 200:
                        return res.json()
                    else:
                        logger.warning(f"⚠️ {name} 응답 에러 (HTTP {res.status_code})")
                except requests.exceptions.ConnectionError:
                    logger.error(f"❌ {name} 연결 실패: 서버를 찾을 수 없습니다 (ConnectionError)")
                except requests.exceptions.Timeout:
                    logger.error(f"❌ {name} 시간 초과: 응답이 너무 늦습니다 (Timeout)")
                except Exception as e:
                    logger.error(f"❌ {name} 알 수 없는 오류: {e}")
                
                if i < max_retries - 1:
                    time.sleep(retry_delay)
            return None

        # 1. 회피 대기 시간 로드
        conf_data = fetch_with_retry(CONFIG_URL, "설정 정보")
        if conf_data:
            self.avoidance_time = conf_data.get("avoidance_wait_time", 5)
            logger.info(f"   - 회피 대기 시간: {self.avoidance_time}초")
        
        # 2. 이동 경로 로드
        plan_data = fetch_with_retry(PLAN_URL, "웨이포인트 경로")
        if plan_data:
            self.patrol_path = plan_data
            logger.info(f"   - 경로 데이터 로드 완료 ({len(self.patrol_path)}개)")
        
        # 3. 전체 상품 정보 로드
        prod_data = fetch_with_retry(LIST_PRODUCTS_URL, "상품 마스터")
        if prod_data:
            self.products = prod_data
            logger.info(f"   - 상품 데이터 로드 완료 ({len(self.products)}개)")

        if conf_data and plan_data and prod_data:
            logger.info("✅ 모든 메모리 데이터 로딩 성공")
            return True
        else:
            logger.error("🚫 데이터 로딩 실패: 일부 데이터를 가져오지 못했습니다.")
            return False

    def send_detection(self, tag_barcode, detected_barcode=None, yolo_class_id=None, confidence=0.98, odom_x=0.0, odom_y=0.0):
        payload = {
            "tag_barcode": tag_barcode,
            "detected_barcode": detected_barcode,
            "yolo_class_id": yolo_class_id,
            "confidence": confidence,
            "odom_x": round(odom_x, 2),
            "odom_y": round(odom_y, 2),
            "timestamp": datetime.now().isoformat()
        }
        try:
            res = requests.post(DETECT_URL, json=payload)
            if res.status_code == 200:
                data = res.json()
                self.current_patrol_id = data.get("patrol_id")
                # 결과 출력 가독성 개선
                item_desc = detected_barcode if detected_barcode else (f"YOLO:{yolo_class_id}" if yolo_class_id is not None else "NO_ITEM")
                self.safe_print(f"   >>> [서버 판정] {data.get('judgment')} (품명: {data.get('product_name', '알수없음')})")
            else:
                self.safe_print(f"   >>> ❌ 서버 응답 오류: {res.status_code}")
        except Exception as e:
            self.safe_print(f"   >>> ❌ 전송 중 오류: {e}")

    def send_pose(self, odom_x, odom_y):
        try:
            requests.post(POSE_URL, json={"odom_x": round(odom_x, 2), "odom_y": round(odom_y, 2)})
        except:
            pass

    def start_patrol(self, remote=False, resume=False):
        if self.status == STATUS_EMERGENCY_STOP and not resume:
            self.safe_print("⚠️ [거부] 비상 정환 상태입니다. 비상 해제를 먼저 수행하세요.")
            return

        if self.status == STATUS_PATROLLING:

            self.safe_print("⚠️ 이미 순찰 중입니다.")
            return

        if not resume:
            self.safe_print("\n" + "="*40)
            self.safe_print("🚀 [순찰 개시] 로봇이 순찰을 시작합니다.")
            self.safe_print("="*40)
            self.last_index = 0 # 처음부터 시작
        else:
            # 비상 해제/재개 시나리오
            
            # 수동으로 3번(재개)을 누른 경우 서버에도 알림
            if not remote:
                try:
                    res = requests.post(f"{BASE_URL}/patrol/resume", timeout=5)
                    if res.status_code == 200:
                        self.safe_print("✅ 서버에 비상 해제 및 재개 신호를 보냈습니다.")
                    else:
                        self.safe_print(f"⚠️ 서버 신호 전송 실패 (상태 코드: {res.status_code})")
                except Exception as e:
                    self.safe_print(f"⚠️ 서버 연결 실패 (오류: {e})")

            # 이미 작동 중이라면 중복 실행 방지
            if self.status == STATUS_PATROLLING:
                return
            
            # 만약 진행 중이었던 순찰 정보(last_index)가 유효한지 확인
            # (last_index가 patrol_path 길이보다 작으면 갈 곳이 남은 것)
            
            # [추가] 기지에 있다면 재개하지 않음 (유령 순찰 방지)
            dist_to_base = (self.current_pos[0]**2 + self.current_pos[1]**2)**0.5
            
            if self.last_index < len(self.patrol_path) and dist_to_base > 0.3:
                self.safe_print("\n" + "="*40)
                self.safe_print(f"⏯️ [순찰 재개] {self.last_index + 1}번 웨이포인트부터 재개합니다.")
                self.safe_print("="*40)
            else:
                self.safe_print("\n🔓 [비상 해제] 현재 위치(기지 근처 또는 완료)에서 비상을 해제합니다.")
                self.status = STATUS_IDLE
                if not remote: self.print_menu()
                return


        if not remote and not resume:
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
        
        # 로봇 현재 위치 유지
        current_x, current_y = self.current_pos
        robot_speed = 0.2 # 0.2 m/sec
        
        # 순찰 시나리오 시뮬레이션 (마지막 인덱스부터 시작)
        for i in range(self.last_index, len(self.patrol_path)):
            if self.status != STATUS_PATROLLING:
                self.safe_print("🛑 순찰이 중단되었습니다.")
                self.last_index = i # 중단된 위치 저장
                self.current_pos = (current_x, current_y)
                if remote: self.print_menu()
                return

            plan = self.patrol_path[i]
            target_x = plan.get('loc_x', 0.0)
            target_y = plan.get('loc_y', 0.0)
            
            # 거리 계산 (Euclidean distance)
            distance = ((target_x - current_x)**2 + (target_y - current_y)**2)**0.5
            move_time = distance / robot_speed
            
            self.safe_print(f"\n[{i+1}/{len(self.patrol_path)}] {plan['waypoint_name']} 이동 중...")
            self.safe_print(f"   - 목적지: ({target_x}, {target_y}) | 거리: {distance:.2f}m | 예상 소요 시간: {move_time:.1f}초")
            
            # 실제 이동 시간만큼 대기 (이동 중 주기적으로 좌표 전송)
            if move_time > 0:
                elapsed = 0
                report_interval = 2.0
                while elapsed < move_time:
                    if self.status != STATUS_PATROLLING:
                        break
                    
                    # 현재 위치 선형 보간 (Linear Interpolation)
                    ratio = min(1.0, elapsed / move_time)
                    temp_x = current_x + (target_x - current_x) * ratio
                    temp_y = current_y + (target_y - current_y) * ratio
                    self.send_pose(temp_x, temp_y)
                    self.current_pos = (temp_x, temp_y)
                    
                    self.interruptible_sleep(min(report_interval, move_time - elapsed))
                    elapsed += report_interval

            if self.status != STATUS_PATROLLING: break

            self.safe_print(f"📍 {plan['waypoint_name']} 도착. 정차 후 스캔 시작...")
            self.current_pos = (target_x, target_y)
            self.send_pose(target_x, target_y)
            if not self.interruptible_sleep(1.5): break
            
            # 현재 위치 업데이트
            current_x, current_y = target_x, target_y
            
            # 판정 시나리오 (70% 정상, 15% 결품, 15% 오진열)
            rand_val = random.random()
            
            if rand_val < 0.7:
                # 1. 정상 (실제 등록된 바코드 전송)
                self.safe_print(f"   [결과] 정상 인식: {plan['product_name']}")
                self.send_detection(plan['barcode_tag'], detected_barcode=plan['product_barcode'], odom_x=current_x, odom_y=current_y)
            
            elif rand_val < 0.85:
                # 2. 미진열/결품 (YOLO ID -1 또는 0 전송)
                missing_id = random.choice([-1, 0])
                self.safe_print(f"   [결과] 상품 미검출 (결품 시나리오) 발생 (YOLO ID: {missing_id})")
                self.send_detection(plan['barcode_tag'], yolo_class_id=missing_id, confidence=0.0, odom_x=current_x, odom_y=current_y)
            
            else:
                # 3. 오진열 (엉뚱한 상품 클래스 전송)
                # 현재 등록된 상품 마스터에서 의도하지 않은 상품의 YOLO ID를 무작위로 선택
                wrong_products = [p for p in self.products if p.get('yolo_class_id') is not None and p.get('yolo_class_id') != plan.get('yolo_class_id')]
                
                if wrong_products:
                    wrong_p = random.choice(wrong_products)
                    wrong_yolo_id = wrong_p['yolo_class_id']
                    self.safe_print(f"   [결과] 오진열 발생! (기대:{plan['product_name']} -> 실제:{wrong_p['product_name']})")
                    self.send_detection(plan['barcode_tag'], yolo_class_id=wrong_yolo_id, confidence=0.95, odom_x=current_x, odom_y=current_y)
                else:
                    # 마땅한 상품이 없으면 아예 모르는 ID 전송
                    self.safe_print(f"   [결과] 알 수 없는 상품 감지 (오진열)")
                    self.send_detection(plan['barcode_tag'], yolo_class_id=999, confidence=0.7, odom_x=current_x, odom_y=current_y)

            # 회피 대기 시나리오 (30% 확률)
            if i < len(self.patrol_path) - 1 and random.random() < 0.3:
                self.safe_print(f"⚠️ [장애물 감지] 이동 경로에 장애물이 있습니다. {self.avoidance_time}초 대기...")
                if not self.interruptible_sleep(self.avoidance_time):
                    break

        if self.status != STATUS_PATROLLING:
            self.safe_print("🛑 순찰이 중단되었습니다.")
            self.last_index = i # 중단된 위치 저장
            self.current_pos = (current_x, current_y)
            if remote: self.print_menu()
            return

        self.last_index = len(self.patrol_path) # 완료 표시
        self.current_pos = (0.0, 0.0) # 복귀했으므로 0,0
        self.return_to_base(remote=remote)

    def return_to_base(self, remote=False):
        # 만약 비상 정지 상태에서 복귀 명령이 왔다면, 비상 해제 후 복귀 수행 (사용자 요청)
        if self.status == STATUS_EMERGENCY_STOP:
            self.safe_print("\n🔓 [비상 해제] 비상 정지 상태에서 기지 복귀 명령을 수신하여 비상을 해제합니다.")
            self.status = STATUS_RETURNING
        
        # 기지(0,0)까지의 거리 및 시간 계산
        current_x, current_y = self.current_pos
        distance = (current_x**2 + current_y**2)**0.5
        robot_speed = 0.2
        travel_time = distance / robot_speed

        if distance < 0.05:
            self.safe_print("\n🏠 [이미 기지] 로봇이 이미 기지(0,0)에 근접해 있습니다.")
            self.status = STATUS_IDLE
            # 기지에서 이미 정지된 상태였다면 즉시 완료 처리
        else:
            self.safe_print(f"\n🏠 [기지 복귀] 기지로 복귀 시작합니다... (거리: {distance:.2f}m, 예상 시간: {travel_time:.1f}초)")
            self.status = STATUS_RETURNING
            if travel_time > 0:
                if not self.interruptible_sleep(travel_time):
                    if self.status == STATUS_EMERGENCY_STOP:
                        self.safe_print("🛑 복귀 중 비상 정지되었습니다.")
                        if remote: self.print_menu()
                        return

        self.safe_print("🏁 [복귀 완료] 로봇이 기지에 도착했습니다.")
        self.status = STATUS_IDLE
        self.current_pos = (0.0, 0.0) # 최종 위치 보정
        self.last_index = len(self.patrol_path) # 유령 순찰 방지를 위해 인덱스 완료 처리
        
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
        # 비상 정지 즉시 현재 위치 서버로 보고
        self.send_pose(self.current_pos[0], self.current_pos[1])
        
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
                        elif cmd_type == "RESUME_PATROL":
                            threading.Thread(target=self.start_patrol, args=(True, True)).start()
                        
                        # 명령 완료 처리 알림
                        if cmd_id:
                            try:
                                requests.post(f"{BASE_URL}/robot/command/{cmd_id}/complete")
                            except:
                                pass
                    
                    # [추가] 대기 중(IDLE)이거나 명령 확인 시마다 현재 좌표와 하트비트 전송 (상시 위치 업데이트)
                    self.send_pose(self.current_pos[0], self.current_pos[1])
                            
            except Exception as e:
                pass
            
            time.sleep(1) # 1초마다 확인 (반응성 향상)

    def run(self):
        # 1. 시작 전 이전 세션의 잔류 명령 초기화 (먹통 및 자동 실행 방지)
        try:
            requests.post(CLEAR_COMMAND_URL, timeout=5)
            self.safe_print("🧹 [초기화] 이전 세션의 대기 중인 명령을 모두 정리했습니다.")
        except Exception:
            pass

        # 2. 서버에서 설정 정보 및 동기화된 상태 읽어오기
        self.load_memory()
        try:
            status_res = requests.get(f"{BASE_URL}/status", timeout=5)
            if status_res.status_code == 200:
                server_status = status_res.json().get("robot_status")
                if server_status == "비상정지":
                    self.status = STATUS_EMERGENCY_STOP
                    self.safe_print("⚠️ [동기화] 현재 서버가 비상 정지 상태입니다. 시뮬레이터도 비상 모드로 시작합니다.")
        except Exception:
            pass

        # 3. 원격 명령 수신 스레드 시작
        self.polling_thread = threading.Thread(target=self.poll_commands, daemon=True)
        self.polling_thread.start()
        
        self.safe_print("="*50)
        self.safe_print("🤖 Gilbot 확장 가상 로봇 시뮬레이터 v2.1")
        self.safe_print("   - 서버 주소: " + BASE_URL)
        self.safe_print("   - 상태: " + self.status)
        self.safe_print("   - 원격 신호 대기 중 (Polling)")
        self.safe_print("="*50)
        
        while True:
            try:
                self.print_menu()
                # Check for tty or if stdin is closed/broken
                if not sys.stdin or not sys.stdin.isatty():
                    self.stop_event.wait(timeout=5)
                    continue

                choice = sys.stdin.readline().strip().lower()
                if not choice:
                    time.sleep(1)
                    continue
            except (OSError, EOFError) as e:
                # Descriptor was likely closed - fallback to polling mode only
                self.safe_print(f"⚠️  Input-Terminal disconnected ({e}). Falling back to Remote-only mode.")
                self.stop_event.wait(timeout=5)
                continue
            except Exception as e:
                time.sleep(5)
                continue
                
            if choice == '1':
                self.start_patrol()
            elif choice == '2':
                self.emergency_stop()
            elif choice == '3':
                threading.Thread(target=self.start_patrol, args=(False, True)).start()
            elif choice == '4':
                self.return_to_base()
            elif choice == '5':
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
