from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal

class LoginWindow(QWidget):
    # 로그인 성공 시 메인 화면으로 넘어가기 위한 신호
    login_success = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # 1. 기본 윈도우 설정
        self.setWindowTitle("RETAIL ROBOT MANAGEMENT SYSTEM - LOGIN")
        self.setFixedSize(850, 650)
        self.setStyleSheet("background-color: #2C3E50; font-family: 'Malgun Gothic';")

        # 2. 메인 레이아웃 설정 (수직 배치)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # 전체 요소를 수직 중앙에 배치
        layout.setSpacing(20)

        # 3. 로고 및 타이틀 (중앙 정렬 적용)
        logo = QLabel("🐱")
        logo.setStyleSheet("font-size: 80px; color: #82E0AA; border: none; margin-bottom: 10px;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_kr = QLabel(" 편돌이 ")
        title_kr.setStyleSheet("font-size: 30px; font-weight: bold; color: white; border: none;")
        title_kr.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 레이아웃에 추가 시 AlignHCenter 명시 (X축 중앙 고정)
        layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title_kr, alignment=Qt.AlignmentFlag.AlignHCenter)

        # 4. 입력 필드 스타일 정의 (너비 고정으로 중앙 정렬 유지)
        self.input_style = """
            QLineEdit {
                background-color: #34495E; border: 2px solid #5D6D7E;
                border-radius: 10px; padding: 12px; color: white; font-size: 16px;
                min-width: 350px; max-width: 350px;
            }
            QLineEdit:focus { border: 2px solid #27AE60; }
        """
        # 에러 발생 시 스타일 (테두리 빨간색)
        self.error_style = self.input_style.replace("#5D6D7E", "#E86464")

        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("👤 아이디 입력")
        self.id_input.setStyleSheet(self.input_style)

        self.pw_input = QLineEdit()
        self.pw_input.setPlaceholderText("🔒 PASSWORD")
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setStyleSheet(self.input_style)

        # 입력 필드들을 레이아웃 가로 중앙에 추가
        layout.addWidget(self.id_input, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.pw_input, alignment=Qt.AlignmentFlag.AlignHCenter)

        # 5. 로그인 버튼 (X축 중앙 정렬의 핵심)
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

        # 버튼 추가 시 가로 중앙 정렬 명시
        layout.addWidget(self.login_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        # 6. 하단 카피라이트 정보
        footer = QLabel("© 2026 RRM Tech. All rights reserved.")
        footer.setStyleSheet("color: #7F8C8D; font-size: 12px; border: none;")
        layout.addSpacing(30)
        layout.addWidget(footer, alignment=Qt.AlignmentFlag.AlignHCenter)

        # 7. 이벤트 연결 (Enter 키 대응 및 클릭 이벤트)
        self.id_input.returnPressed.connect(self.validate_login)
        self.pw_input.returnPressed.connect(self.validate_login)
        self.login_btn.clicked.connect(self.validate_login)

    def validate_login(self):
        """
        아이디 'admin' / 비밀번호 '1234' 검증 로직
        """
        user_id = self.id_input.text().strip()
        user_pw = self.pw_input.text().strip()

        if user_id == "admin" and user_pw == "1234":
            print("로그인 성공: 메인 시스템으로 이동합니다.")
            self.login_success.emit() # 메인 화면 전환 신호 발생
        else:
            # 로그인 실패 시 시각적 피드백 (빨간 테두리)
            print("로그인 실패: 정보를 확인하세요.")
            self.id_input.setStyleSheet(self.error_style)
            self.pw_input.setStyleSheet(self.error_style)
            self.pw_input.clear()
            self.pw_input.setPlaceholderText("비밀번호가 틀렸습니다")
