import sys
from PyQt6.QtWidgets import QApplication
from robot_login import LoginWindow      # 새로 만든 로그인 UI
from robot_ui import RobotControlPanel    # 기존 메인 UI
from robot_logic import RobotLogicHandler # 기존 로직 핸들러

class MainApp:
    def __init__(self):
        # 1. 로그인 창 생성 및 표시
        self.login_view = LoginWindow()
        self.login_view.login_success.connect(self.start_main_system)
        self.login_view.show()

    def start_main_system(self):
        # 2. 로그인 창 닫기
        self.login_view.close()

        # 3. 메인 UI 생성 (기존 main 함수 내용)
        self.main_view = RobotControlPanel()

        # 4. 로직을 UI에 연결 (기존 main 함수 내용)
        self.logic = RobotLogicHandler(self.main_view)

        # 5. 메인 화면 표시
        self.main_view.show()

def main():
    app = QApplication(sys.argv)

    # 앱 제어 클래스 실행
    manager = MainApp()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
