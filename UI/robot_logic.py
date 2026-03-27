class RobotLogicHandler:
    def __init__(self, ui_instance):
        self.ui = ui_instance
        self._setup_connections()
        self._load_initial_data()

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
        # 예: 마지막 순찰 시간을 DB에서 조회해서 UI에 표시
        dummy_time = "2026:03:27:14:30:05"
        self.ui.set_last_patrol_time(dummy_time)

    # --- [핸들러 함수들: 담당자들이 내용을 채울 부분] ---

    def on_patrol_set(self, val):
        print(f"[LOGIC] 서버로 순찰 시간 {val}분 설정 패킷 송신")

    def on_obstacle_set(self, val):
        print(f"[LOGIC] 장애물 인식 대기 시간 {val}초로 변경")

    def on_move_command(self, direction):
        print(f"[LOGIC] 로봇 구동 명령: {direction}")
        # 여기에 socket 통신이나 ROS2 topic 발행 코드 작성

    def on_buzzer(self):
        print("[LOGIC] 부저 ON 명령 발생")

    def on_return_patrol(self):
        print("[LOGIC] 순찰 복귀 시퀀스 시작")

    def on_emergency(self):
        print("[LOGIC] !!! 하드웨어 비상 정지 신호 송신 !!!")

    def on_reset_confirmed(self):
        print("[LOGIC] 로봇 원점 복귀 명령")

    def update_inventory_db(self):
        """DB에서 재고 데이터를 가져와 테이블에 뿌려줌"""
        print("[LOGIC] 재고 DB 조회 중...")
        # 실제 구현 시: data = db.query("SELECT * FROM inventory")
        # 현재는 UI에서 제공하는 set_db_data(None) 호출 시 더미데이터가 나옵니다.
        self.ui.set_db_data(None)

    def update_alarm_list(self):
        """재고 부족 물품 리스트 업데이트"""
        print("[LOGIC] 재고 알림 리스트 갱신 중...")
        self.ui.set_alarm_data(None)
