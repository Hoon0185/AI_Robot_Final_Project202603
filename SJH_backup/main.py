import sys
from PyQt6.QtWidgets import QApplication
from robot_login import LoginWindow      # 로그인 UI
from robot_ui import RobotControlPanel    # 메인 UI 도화지
from robot_logic import RobotLogicHandler # 로직 처리 담당

class MainApp:
    def __init__(self):
        # 1. 로그인 창 생성 및 표시
        self.login_view = LoginWindow()
        # 로그인 성공 시 전달되는 bool 값(is_debug)을 받을 수 있도록 연결
        self.login_view.login_success.connect(self.start_main_system)
        self.login_view.show()

    def start_main_system(self, is_debug):
        """
        로그인 성공 시 호출되는 함수
        :param is_debug: True(디버그 모드), False(릴리즈 모드)
        """
        # 2. 로그인 창 닫기
        self.login_view.close()

        # 3. 메인 UI 생성
        self.main_view = RobotControlPanel()

        # 4. 로직 핸들러 생성 및 UI 연결
        # 선택된 모드(is_debug)를 핸들러에 전달하여 미니맵 및 제어 방식을 결정합니다.
        self.logic = RobotLogicHandler(self.main_view, debug_mode=is_debug)

        # 5. 메인 화면 표시
        self.main_view.show()

def main():
    app = QApplication(sys.argv)
    manager = MainApp()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
