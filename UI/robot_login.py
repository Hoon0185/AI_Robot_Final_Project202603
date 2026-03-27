from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal

class LoginWindow(QWidget):
    login_success = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("RETAIL ROBOT MANAGEMENT SYSTEM - LOGIN")
        self.setFixedSize(850, 650)
        self.setStyleSheet("background-color: #2C3E50; font-family: 'Malgun Gothic';")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        logo = QLabel("🐱")
        logo.setStyleSheet("font-size: 80px; color: #82E0AA; border: none; margin-bottom: 10px;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_kr = QLabel(" 편돌이 ")
        title_kr.setStyleSheet("font-size: 30px; font-weight: bold; color: white; border: none;")
        title_kr.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title_kr, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.input_style = """
            QLineEdit {
                background-color: #34495E; border: 2px solid #5D6D7E;
                border-radius: 10px; padding: 12px; color: white; font-size: 16px;
                min-width: 350px; max-width: 350px;
            }
            QLineEdit:focus { border: 2px solid #27AE60; }
        """
        self.error_style = self.input_style.replace("#5D6D7E", "#E86464")

        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("👤 아이디 입력")
        self.id_input.setStyleSheet(self.input_style)

        self.pw_input = QLineEdit()
        self.pw_input.setPlaceholderText("🔒 PASSWORD")
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setStyleSheet(self.input_style)

        layout.addWidget(self.id_input, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.pw_input, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.login_btn = QPushButton("로그인")
        self.login_btn.setFixedSize(350, 55)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #27AE60; color: white; border-radius: 12px;
                font-size: 20px; font-weight: bold;
            }
            QPushButton:hover { background-color: #2ECC71; }
            QPushButton:pressed { padding-top: 5px; padding-left: 5px; }
        """)

        layout.addWidget(self.login_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        footer = QLabel("© 2026 RRM Tech. All rights reserved.")
        footer.setStyleSheet("color: #7F8C8D; font-size: 12px; border: none;")
        layout.addSpacing(30)
        layout.addWidget(footer, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.id_input.returnPressed.connect(self.validate_login)
        self.pw_input.returnPressed.connect(self.validate_login)
        self.login_btn.clicked.connect(self.validate_login)

    def validate_login(self):
        user_id = self.id_input.text().strip()
        user_pw = self.pw_input.text().strip()

        if user_id == "admin" and user_pw == "1234":
            self.login_success.emit()
        else:
            self.id_input.setStyleSheet(self.error_style)
            self.pw_input.setStyleSheet(self.error_style)
            self.pw_input.clear()
            self.pw_input.setPlaceholderText("비밀번호가 틀렸습니다")
