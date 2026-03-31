import rclpy
from PyQt6.QtCore import QTimer
from manual_Control import ManualController # 수동 조작 노드
from minimap import MinimapHandler           # 미니맵 처리 노드

class RobotLogicHandler:
    def __init__(self, ui_instance, debug_mode=True):
        """
        :param ui_instance: robot_ui.py의 RobotControlPanel 인스턴스
        :param debug_mode: 로그인 화면에서 선택된 모드 (True: Debug, False: Release)
        """
        self.ui = ui_instance
        self.is_debug = debug_mode  # 선택된 모드 저장

        # --- [ROS 2 초기화] ---
        if not rclpy.ok():
            rclpy.init()

        # 1. 수동 제어 노드 생성
        self.ros_control = ManualController()

        # 2. 미니맵 핸들러 생성 (UI의 label_map_display와 연결)
        # 로그인 시 선택한 debug_mode 값을 그대로 전달합니다.
        self.minimap = MinimapHandler(self.ui.label_map_display, debug_mode=self.is_debug)

        # --- [ROS 통신 유지를 위한 타이머] ---
        # 10ms마다 spin_once를 호출하여 메시지를 주고받습니다.
        self.ros_timer = QTimer()
        self.ros_timer.timeout.connect(self._ros_spin_once)
        self.ros_timer.start(10)

        self._setup_connections()
        self._load_initial_data()

    def _ros_spin_once(self):
        """
        두 개의 ROS 노드(제어, 미니맵)가 동시에 동작하도록
        교대로 spin_once를 수행합니다.
        """
        if rclpy.ok():
            # 수동 조작 노드 처리
            rclpy.spin_once(self.ros_control, timeout_sec=0)
            # 미니맵/맵 데이터 처리
            rclpy.spin_once(self.minimap, timeout_sec=0)

    def _setup_connections(self):
        """ UI(robot_ui.py)에서 정의된 시그널들을 실제 로직 함수에 연결합니다. """
        # 설정 관련
        self.ui.patrolTimeConfirmed.connect(self.on_patrol_set)
        self.ui.obstacleConfirmed.connect(self.on_obstacle_set)

        # 수동 제어 관련
        self.ui.moveCommand.connect(self.on_move_command)      # 방향키 조작
        self.ui.buzzerClicked.connect(self.on_buzzer)           # 부저 제어
        self.ui.returnClicked.connect(self.on_return_patrol)    # 순찰 복귀
        self.ui.emergencyClicked.connect(self.on_emergency)     # 비상 정지
        self.ui.resetConfirmed.connect(self.on_reset_confirmed) # 처음 위치로

        # DB 및 알림 갱신 요청
        self.ui.dbRefreshRequested.connect(self.update_inventory_db)
        self.ui.alarmRefreshRequested.connect(self.update_alarm_list)

        # 맵 버튼 클릭 시 동작 (추가 로직이 필요할 경우)
        self.ui.map_btn.clicked.connect(self.on_map_open)

    def _load_initial_data(self):
        """[원본 유지] 앱 시작 시 초기 데이터를 DB에서 가져와 UI에 세팅"""
        # 실제 구현 시 DB 쿼리 결과가 들어갈 자리입니다.
        dummy_time = "2026:03:27:14:30:05"
        self.ui.set_last_patrol_time(dummy_time)

    # --- [핸들러 함수들] ---

    def on_map_open(self):
        """ 맵 팝업이 열릴 때 실행되는 로직 """
        mode_str = "DEBUG" if self.is_debug else "RELEASE"
        print(f"[LOGIC] 맵 오픈 - 현재 모드: {mode_str}")

        # 디버그 모드라면 버튼 누를 때마다 가상 맵을 갱신해줍니다.
        if self.is_debug:
            self.minimap._generate_debug_map()

    def on_patrol_set(self, val):
        print(f"[LOGIC] 서버로 순찰 시간 {val}분 설정 패킷 송신")

    def on_obstacle_set(self, val):
        print(f"[LOGIC] 장애물 인식 대기 시간 {val}초로 변경")

    def on_move_command(self, direction):
        """ 수동 조작 버튼 클릭 시 호출 """
        if self.ros_control.is_connected:
            print(f"[LOGIC] 로봇 구동 명령 전송: {direction}")
            self.ros_control.move_robot(direction)
        else:
            # 로봇 미연결 시 로그 출력
            print(f"[DEBUG-MODE] 로봇 미연결 상태 - {direction} 명령 시뮬레이션 중")

    def on_buzzer(self):
        """ 부저 버튼 클릭 시 호출 """
        print("[LOGIC] 부저 ON 명령 발생")
        if self.ros_control.is_connected:
            self.ros_control.play_sound("ON")
        else:
            print("[DEBUG-MODE] 로봇 미연결 상태 - 부저 작동 시뮬레이션")

    def on_return_patrol(self):
        """ 순찰 복귀 명령 시 호출 """
        print("[LOGIC] 순찰 복귀 시퀀스 시작")

    def on_emergency(self):
        """ 비상 정지 버튼 클릭 시 호출 """
        print("[LOGIC] !!! 비상 정지 신호 !!!")
        self.ros_control.stop_robot()

    def on_reset_confirmed(self):
        """ 로봇 원점 복귀 명령 시 호출 """
        print("[LOGIC] 로봇 원점 복귀 명령")

    def update_inventory_db(self):
        """ 재고 조회 패널 오픈 시 데이터 갱신 """
        print("[LOGIC] 재고 DB 조회 중...")
        # 현재는 데이터가 없으므로 None 전달 (ui에서 기본값 처리)
        self.ui.set_db_data(None)

    def update_alarm_list(self):
        """ 재고 알림 패널 오픈 시 데이터 갱신 """
        print("[LOGIC] 재고 알림 리스트 갱신 중...")
        # 현재는 데이터가 없으므로 None 전달 (ui에서 기본값 처리)
        self.ui.set_alarm_data(None)
