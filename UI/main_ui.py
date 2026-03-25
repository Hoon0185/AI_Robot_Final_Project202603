import sys
from PyQt6.QtWidgets import QApplication
from robot_ui import RobotControlPanel
from robot_logic import RobotLogicHandler

def main():
    app = QApplication(sys.argv)

    # UI 생성
    view = RobotControlPanel()

    # 로직을 UI에 연결
    logic = RobotLogicHandler(view)

    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
