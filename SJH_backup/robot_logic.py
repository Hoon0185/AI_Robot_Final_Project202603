import sys
import os

# ROS 2 패키지 경로 추가 (logic01/src/patrol_main 하위의 모듈을 참조하기 위함)
current_dir = os.path.dirname(os.path.abspath(__file__))
patrol_main_path = os.path.join(current_dir, 'logic01', 'src', 'patrol_main')
if patrol_main_path not in sys.path:
    sys.path.append(patrol_main_path)

try:
    from patrol_main.patrol_interface import PatrolInterface
except ImportError:
    # 패키지 구조에 따라 직접 참조가 필요한 경우 하드코딩된 경로 추가
    sys.path.append(os.path.join(patrol_main_path, 'patrol_main'))
    try:
        from patrol_interface import PatrolInterface
    except ImportError:
        # 디버그 모드를 위해 임포트 실패 시 pass 처리 (is_debug에서 걸러짐)
        PatrolInterface = None

class RobotLogicHandler:
    def __init__(self, ui_instance, debug_mode=False):
        self.ui = ui_instance
        self.is_debug = debug_mode # 디버그 모드 상태 저장

        # ROS 2 인터페이스 초기화 (디버그 모드가 아닐 때만 시도)
        self.ros_interface = None
        if not self.is_debug:
            try:
                if PatrolInterface:
                    self.ros_interface = PatrolInterface()
                else:
                    raise ImportError("PatrolInterface module not found.")
            except Exception as e:
                print(f"[ERROR] ROS 2 Interface failed to start: {e}")
                print("[SYSTEM] 릴리즈 모드에서 연결 실패. 하드웨어를 확인하세요.")
        else:
            print("[SYSTEM] DEBUG MODE 활성화: 외부 연결(ROS/DB) 없이 시뮬레이션 데이터를 사용합니다.")

        self._setup_connections()
        self.current_patrol_min = 60
        self.current_obstacle_sec = 10
        self._load_initial_data()

        # UI 업데이트용 타이머 (ROS 상태 반영)
        from PyQt6.QtCore import QTimer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.sync_ros_status)
        # 맵 실시간 위치 동기화 함수 추가 연결
        self.status_timer.timeout.connect(self.update_minimap_pose)
        self.status_timer.start(1000) # 1초마다 동기화

    def _setup_connections(self):
        """
        UI(robot_ui.py)에서 정의된 시그널들을 실제 로직 함수에 연결합니다.
        UI 코드를 직접 수정하지 않고도 여기서 모든 제어가 가능합니다.
        """
        # 설정 관련
        self.ui.patrolTimeConfirmed.connect(self.on_patrol_set)
        self.ui.obstacleConfirmed.connect(self.on_obstacle_set)

        # 수동 제어 관련
        self.ui.moveCommand.connect(self.on_move_command)
        self.ui.buzzerClicked.connect(self.on_buzzer)
        self.ui.returnClicked.connect(self.on_return_patrol)
        self.ui.emergencyClicked.connect(self.on_emergency)
        self.ui.resetConfirmed.connect(self.on_reset_confirmed)

        # --- 추가: 수동 순찰 명령 시그널 연결 ---
        self.ui.patrolConfirmed.connect(self.on_patrol_confirmed)

        # DB 및 알림 갱신 요청
        self.ui.dbRefreshRequested.connect(self.update_inventory_db)
        self.ui.alarmRefreshRequested.connect(self.update_alarm_list)

    def _load_initial_data(self):
        """앱 시작 시 초기 데이터를 DB에서 가져와 UI 및 ROS에 세팅"""
        self.update_inventory_db()
        self.update_alarm_list()

        # 서버에서 초기 설정값 가져와서 ROS 및 UI 동기화
        if self.ros_interface:
            config = self.ros_interface.get_db_config()
            if config:
                print(f"[LOGIC] 서버에서 초기 설정 로드: {config}")
                try:
                    # 1. 장애물 대기 시간 (UI 값 설정)
                    self.current_obstacle_sec = config.get('avoidance_wait_time', 10)
                    self.ui.obstacle_row['slider'].setValue(self.current_obstacle_sec)

                    # 2. 순찰 간격 (UI 값 설정 및 ROS 파라미터 적용)
                    h = config.get('interval_hour', 0)
                    m = config.get('interval_minute', 0)
                    self.current_patrol_min = h * 60 + m
                    if self.current_patrol_min > 0:
                        self.ui.patrol_row['slider'].setValue(self.current_patrol_min)
                        self.ros_interface.set_patrol_interval(float(self.current_patrol_min))

                except Exception as e:
                    print(f"[ERROR] 초기 설정 반영 중 오류: {e}")
        elif self.is_debug:
            # 디버그 모드 시 기본 UI 초기값 설정
            print("[DEBUG] 초기 UI 데이터를 가상으로 세팅합니다.")
            self.ui.obstacle_row['slider'].setValue(10)
            self.ui.patrol_row['slider'].setValue(60)

    def sync_ros_status(self):
        """ROS에서 넘어온 최신 상태 또는 DB 로그를 UI에 반영합니다."""
        if self.is_debug:
            # 디버그 모드 가상 상태 표시
            self.ui.set_last_patrol_time("2026-03-31 16:30 (DEBUG MODE ACTIVE)")
            return

        if not self.ros_interface: return

        status = self.ros_interface.get_recent_patrol_time()
        if status:
            # 마지막 순찰 시간 및 상태 표시
            time_info = status.get('start_time', 'No Data')
            s_type = status.get('status', 'IDLE')

            if s_type == 'patrolling':
                shelf = status.get('current_shelf', 'Moving...')
                progress = status.get('progress', '')
                display_text = f"{time_info} (순찰 중: {shelf} {progress})"
            else:
                display_text = f"{time_info} ({s_type})"

            self.ui.set_last_patrol_time(display_text)

    # --- [핸들러 함수들: 담당자들이 내용을 채울 부분] ---

    def on_patrol_set(self, val):
        """순찰 간격 설정 (상태 유지하며 DB 동기화)"""
        self.current_patrol_min = int(val)
        h, m = divmod(self.current_patrol_min, 60)
        print(f"[LOGIC] 순찰 간격 {val}분 설정 ({h}시간 {m}분)")

        if self.ros_interface:
            # 1. ROS 파라미터 업데이트
            self.ros_interface.set_patrol_interval(float(val))
            # 2. DB 서버 업데이트 (현재 장애물 대기 시간 유지)
            self.ros_interface.sync_config_to_db(
                avoidance_wait=self.current_obstacle_sec,
                hour=h,
                minute=m
            )
        elif self.is_debug:
            print(f"[DEBUG] DB 연결 없이 설정값 로컬 업데이트: {h}h {m}m")

    def on_obstacle_set(self, val):
        """장애물 대기 시간 설정 (상태 유지하며 DB 동기화)"""
        self.current_obstacle_sec = int(val)
        h, m = divmod(self.current_patrol_min, 60)
        print(f"[LOGIC] 장애물 대기 시간 {val}초 설정 (순찰 간격 {h}:{m} 유지)")

        if self.ros_interface:
            # DB 서버 업데이트 (현재 순찰 간격 유지)
            self.ros_interface.sync_config_to_db(
                avoidance_wait=self.current_obstacle_sec,
                hour=h,
                minute=m
            )
        elif self.is_debug:
            print(f"[DEBUG] DB 연결 없이 장애물 대기 시간 업데이트: {val}s")

    # 재고 알림
    def update_alarm_list(self):
        """재고 부족 물품 리스트 업데이트"""
        if self.ros_interface:
            data = self.ros_interface.get_alarm_data()
            self.ui.set_alarm_data(data)
        elif self.is_debug:
            # 디버그용 샘플 데이터
            debug_data = [("가상 상품A", "부족"), ("가상 상품B", "품절")]
            self.ui.set_alarm_data(debug_data)

    # DB 재고 조회
    def update_inventory_db(self):
        """DB에서 재고 데이터를 가져와 테이블에 뿌려줌"""
        if self.ros_interface:
            data = self.ros_interface.get_inventory_data()
            self.ui.set_db_data(data)
        elif self.is_debug:
            # 디버그용 샘플 데이터
            debug_data = [("1", "가상 상품A", "10", "A-1"), ("2", "가상 상품B", "0", "B-2")]
            self.ui.set_db_data(debug_data)

    # 수동 조작 패널 - 수동 조작
    def on_move_command(self, direction):
        print(f"[LOGIC] 수동 이동: {direction}")
        if self.ros_interface:
            self.ros_interface.move_robot(direction)
        elif self.is_debug:
            print(f"[DEBUG] Robot moving to {direction}")

    # 수동 조작 패널 - 부저
    def on_buzzer(self):
        print("[LOGIC] 부저 작동")
        if self.ros_interface:
            self.ros_interface.trigger_buzzer(True)
        elif self.is_debug:
            print("[DEBUG] Buzzer sound activated")

    # 수동 조작 패널 - 복귀 명령
    def on_return_patrol(self):
        print("[LOGIC] 복귀 명령 송출")
        if self.ros_interface:
            self.ros_interface.return_to_base()
        elif self.is_debug:
            print("[DEBUG] Returning to home station")

    # 수동 조작 패널 - 비상 정지
    def on_emergency(self):
        print("[LOGIC] 비상 정지!")
        if self.ros_interface:
            self.ros_interface.trigger_emergency_stop()
        elif self.is_debug:
            print("[DEBUG] EMERGENCY STOP TRIGGERED")

    # 초기 위치 명령 패널 - 예 - 복귀
    # 기능은 수동 조작 패널의 복귀 명령과 같음
    def on_reset_confirmed(self):
        print("[LOGIC] 원점 리셋")
        if self.ros_interface:
            self.ros_interface.reset_position()
        elif self.is_debug:
            print("[DEBUG] Resetting to origin")

    # 수동 순찰 명령
    def on_patrol_confirmed(self):
        """수동 순찰 명령 팝업에서 '시작'을 클릭했을 때 호출"""
        print("[LOGIC] 수동 순찰 명령 확인됨. 순찰 로직 시작 프로세스 수행 가능.")
        if self.ros_interface:
            # TODO: 담당자 구현 영역 (예: 순찰 노드 활성화 신호 송출 등)
            pass
        elif self.is_debug:
            print("[DEBUG] Manual patrol sequence started in simulation")

# --- 맵 패널 업데이트 로직 추가 ---
    def update_minimap_pose(self):
        """ROS 실시간 좌표를 가져와 MinimapWidget(minimap.py)에 반영합니다."""

        # UI 인스턴스에 minimap 위젯이 실제로 존재하는지 먼저 확인
        if not hasattr(self.ui, 'minimap') or self.ui.minimap is None:
            # print("[DEBUG] UI에 minimap 객체가 없습니다.") # 확인용 (필요시 주석 해제)
            return

        if self.is_debug:
            # 디버그 모드일 때 미니맵에 가상 로봇 위치(0,0) 전송
            # print("[DEBUG] 미니맵 디버그 좌표 전송 시도")
            self.ui.minimap.set_robot_pose(0.0, 0.0)
            return

        if not self.ros_interface:
            return

        # 인터페이스로부터 최신 상태 데이터 획득
        status = self.ros_interface.get_recent_patrol_time()

        # 데이터가 있고, 내부에 좌표 정보(예: robot_x, robot_y)가 포함되어 있다면 미니맵 갱신
        if status and 'robot_x' in status and 'robot_y' in status:
            curr_x = status.get('robot_x', 0.0)
            curr_y = status.get('robot_y', 0.0)
            self.ui.minimap.set_robot_pose(curr_x, curr_y)
        else:
            # 좌표 데이터가 없을 때도 맵 자체는 보여야 하므로 강제 업데이트 호출
            # 이 코드가 없으면 로봇 위치가 올 때까지 맵이 안 뜰 수 있습니다.
            self.ui.minimap.update_map_display()
