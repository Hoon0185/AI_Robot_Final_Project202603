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
    from patrol_interface import PatrolInterface

class RobotLogicHandler:
    def __init__(self, ui_instance):
        self.ui = ui_instance
        # ROS 2 인터페이스 초기화
        try:
            self.ros_interface = PatrolInterface()
        except Exception as e:
            print(f"[ERROR] ROS 2 Interface failed to start: {e}")
            self.ros_interface = None
            
        self._setup_connections()
        self._load_initial_data()
        
        # UI 업데이트용 타이머 (ROS 상태 반영)
        from PyQt6.QtCore import QTimer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.sync_ros_status)
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

        # DB 및 알림 갱신 요청
        self.ui.dbRefreshRequested.connect(self.update_inventory_db)
        self.ui.alarmRefreshRequested.connect(self.update_alarm_list)

    def _load_initial_data(self):
        """앱 시작 시 초기 데이터를 DB에서 가져와 UI에 세팅"""
        self.update_inventory_db()
        self.update_alarm_list()
        
        # 서버에서 초기 설정값 가져오기
        if self.ros_interface:
            config = self.ros_interface.get_db_config()
            if config:
                print(f"[LOGIC] 서버에서 설정값 로드: {config}")
                # UI에 설정값 반영 (UI 구성에 따라 다름)
                try:
                    interval = config.get('interval_hour', 0) * 60 + config.get('interval_minute', 0)
                    self.ui.set_patrol_interval_ui(interval) 
                except Exception:
                    pass

    def sync_ros_status(self):
        """ROS에서 넘어온 최신 상태 또는 DB 로그를 UI에 반영합니다."""
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
        print(f"[LOGIC] 순찰 간격 {val}분 설정 (ROS + DB 동기화)")
        if self.ros_interface:
            # 1. ROS 파라미터 업데이트
            self.ros_interface.set_patrol_interval(val)
            # 2. DB 서버 업데이트
            self.ros_interface.sync_config_to_db(minute=val)

    def on_obstacle_set(self, val):
        print(f"[LOGIC] 장애물 대기 시간 {val}초 설정 (ROS + DB 동기화)")
        if self.ros_interface:
            # DB 서버 업데이트
            self.ros_interface.sync_config_to_db(avoidance_wait=val)

    def on_move_command(self, direction):
        print(f"[LOGIC] 수동 이동: {direction}")
        if self.ros_interface:
            self.ros_interface.move_robot(direction)

    def on_buzzer(self):
        print("[LOGIC] 부저 작동")
        if self.ros_interface:
            self.ros_interface.trigger_buzzer(True)

    def on_return_patrol(self):
        print("[LOGIC] 복귀 명령 송출")
        if self.ros_interface:
            self.ros_interface.return_to_base()

    def on_emergency(self):
        print("[LOGIC] 비상 정지!")
        if self.ros_interface:
            self.ros_interface.trigger_emergency_stop()

    def on_reset_confirmed(self):
        print("[LOGIC] 원점 리셋")
        if self.ros_interface:
            self.ros_interface.reset_position()

    def update_inventory_db(self):
        """DB에서 재고 데이터를 가져와 테이블에 뿌려줌"""
        if self.ros_interface:
            data = self.ros_interface.get_inventory_data()
            self.ui.set_db_data(data)

    def update_alarm_list(self):
        """재고 부족 물품 리스트 업데이트"""
        if self.ros_interface:
            data = self.ros_interface.get_alarm_data()
            self.ui.set_alarm_data(data)
