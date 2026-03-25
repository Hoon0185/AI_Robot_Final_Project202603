class RobotLogicHandler:
    def __init__(self, ui_instance):
        self.ui = ui_instance
        self._setup_connections()

    def _setup_connections(self):
        """UI에서 정의한 시그널들을 실제 로직 함수에 연결"""
        self.ui.patrolTimeConfirmed.connect(self.on_patrol_set)
        self.ui.obstacleConfirmed.connect(self.on_obstacle_set)
        self.ui.moveCommand.connect(self.on_move_command)
        self.ui.buzzerClicked.connect(self.on_buzzer)
        self.ui.returnClicked.connect(self.on_return_patrol)
        self.ui.emergencyClicked.connect(self.on_emergency)
        self.ui.resetConfirmed.connect(self.on_reset_confirmed)

    def on_patrol_set(self, val):
        print(f"[LOGIC] 순찰 시간 {val}분으로 서버 전송 중...")

    def on_obstacle_set(self, val):
        print(f"[LOGIC] 장애물 인식 거리 {val}초로 설정 완료")

    def on_move_command(self, direction):
        print(f"[LOGIC] 로봇 이동 제어: {direction}")

    def on_buzzer(self):
        print("[LOGIC] 부저 작동 신호 발생!")

    def on_return_patrol(self):
        print("[LOGIC] 현재 작업 중단 후 순찰 경로 복귀")

    def on_emergency(self):
        print("[LOGIC] !!! 비상 정지 명령 패킷 송신 !!!")

    def on_reset_confirmed(self):
        print("[LOGIC] 초기 위치 복귀 프로세스 시작")
