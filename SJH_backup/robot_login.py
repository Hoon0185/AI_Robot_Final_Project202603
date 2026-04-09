from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal

class LoginWindow(QWidget):
<<<<<<< HEAD
    # 로그인 성공 시 모드(True: Debug, False: Release)를 전달
=======
    # 로그인 성공 시 모드(True: Debug, False: Release)를 전달하도록 인자 추가
>>>>>>> 8442dde4573edfc7ce551e9a80d91eb57b95dce0
    login_success = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
<<<<<<< HEAD
        self.setWindowTitle("ROBOT MANAGEMENT SYSTEM - LOGIN")
        self.setFixedSize(850, 650)
        self.setStyleSheet("background-color: #2C3E50; font-family: 'Malgun Gothic';")

        # 메인 레이아웃 (수직)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 20, 30, 30)

        # --- [1. 우측 상단 모드 선택 영역] ---
        top_h_layout = QHBoxLayout()
        top_h_layout.addStretch() # 왼쪽을 밀어서 우측으로 배치

        self.mode_selector = QComboBox()
        self.mode_selector.addItems(["🛠 DEBUG MODE", "🚀 RELEASE MODE"])
        self.mode_selector.setFixedSize(160, 35) # 크기 최적화

        # 드롭다운 디자인 개선 (어색함 해결)
        self.mode_selector.setStyleSheet("""
            QComboBox {
                background-color: rgba(52, 73, 94, 0.8);
                border: 1px solid #5D6D7E;
                border-radius: 5px;
                padding-left: 10px;
                color: #82E0AA;
                font-size: 12px;
                font-weight: bold;
            }
            QComboBox:hover { border: 1px solid #27AE60; background-color: #34495E; }
            QComboBox::drop-down { border: none; width: 25px; }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #82E0AA;
                margin-top: 2px;
            }
=======
        self.setWindowTitle("RETAIL ROBOT MANAGEMENT SYSTEM - LOGIN")
        self.setFixedSize(850, 650)
        self.setStyleSheet("background-color: #2C3E50; font-family: 'Malgun Gothic';")

        # 메인 레이아웃 (기존 layout을 유지하되 모드 선택기를 위해 전체 배치를 잡습니다)
        main_v_layout = QVBoxLayout(self)

        # --- [추가: 우상단 모드 선택 영역] ---
        top_h_layout = QHBoxLayout()
        top_h_layout.addStretch() # 왼쪽 공간을 다 채워서 ComboBox를 오른쪽 끝으로 밈

        self.mode_selector = QComboBox()
        self.mode_selector.addItems(["🛠 DEBUG MODE", "🚀 RELEASE MODE"])
        self.mode_selector.setFixedSize(150, 30)
        self.mode_selector.setStyleSheet("""
            QComboBox {
                background-color: rgba(52, 73, 94, 0.7);
                border: 1px solid #5D6D7E;
                border-radius: 5px;
                color: #82E0AA;
                font-size: 11px;
                font-weight: bold;
                padding-left: 5px;
            }
            QComboBox:hover { border: 1px solid #27AE60; }
            QComboBox::drop-down { border: none; }
>>>>>>> 8442dde4573edfc7ce551e9a80d91eb57b95dce0
            QAbstractItemView {
                background-color: #34495E;
                color: white;
                selection-background-color: #27AE60;
                outline: none;
<<<<<<< HEAD
                border: 1px solid #5D6D7E;
            }
        """)
        top_h_layout.addWidget(self.mode_selector)
        self.main_layout.addLayout(top_h_layout)

        # --- [2. 중앙 로그인 영역] ---
        center_layout = QVBoxLayout()
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.setSpacing(20)
=======
            }
        """)
        top_h_layout.addWidget(self.mode_selector)
        main_v_layout.addLayout(top_h_layout)

        # 중앙 배치를 위한 컨테이너 레이아웃 (기존 layout 로직 그대로 유지)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
>>>>>>> 8442dde4573edfc7ce551e9a80d91eb57b95dce0

        logo = QLabel("🐱")
        logo.setStyleSheet("font-size: 80px; color: #82E0AA; border: none; margin-bottom: 10px;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_kr = QLabel(" 편돌이 ")
        title_kr.setStyleSheet("font-size: 30px; font-weight: bold; color: white; border: none;")
        title_kr.setAlignment(Qt.AlignmentFlag.AlignCenter)

<<<<<<< HEAD
        center_layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)
        center_layout.addWidget(title_kr, alignment=Qt.AlignmentFlag.AlignHCenter)
=======
        layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title_kr, alignment=Qt.AlignmentFlag.AlignHCenter)
>>>>>>> 8442dde4573edfc7ce551e9a80d91eb57b95dce0

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
<<<<<<< HEAD
        self.id_input.setPlaceholderText("👤 INPUT ID")
=======
        self.id_input.setPlaceholderText("👤 아이디 입력")
>>>>>>> 8442dde4573edfc7ce551e9a80d91eb57b95dce0
        self.id_input.setStyleSheet(self.input_style)

        self.pw_input = QLineEdit()
        self.pw_input.setPlaceholderText("🔒 PASSWORD")
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setStyleSheet(self.input_style)

<<<<<<< HEAD
        center_layout.addWidget(self.id_input, alignment=Qt.AlignmentFlag.AlignHCenter)
        center_layout.addWidget(self.pw_input, alignment=Qt.AlignmentFlag.AlignHCenter)
=======
        layout.addWidget(self.id_input, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.pw_input, alignment=Qt.AlignmentFlag.AlignHCenter)
>>>>>>> 8442dde4573edfc7ce551e9a80d91eb57b95dce0

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

<<<<<<< HEAD
        center_layout.addWidget(self.login_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.main_layout.addLayout(center_layout)

        # --- [3. 푸터 영역] ---
        footer = QLabel("© 2026 RRM Tech. All rights reserved.")
        footer.setStyleSheet("color: #7F8C8D; font-size: 12px; border: none;")
        self.main_layout.addSpacing(30)
        self.main_layout.addWidget(footer, alignment=Qt.AlignmentFlag.AlignHCenter)

        # 이벤트 연결
=======
        layout.addWidget(self.login_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        footer = QLabel("© 2026 RRM Tech. All rights reserved.")
        footer.setStyleSheet("color: #7F8C8D; font-size: 12px; border: none;")
        layout.addSpacing(30)
        layout.addWidget(footer, alignment=Qt.AlignmentFlag.AlignHCenter)

        # 중앙 레이아웃을 메인 레이아웃에 추가
        main_v_layout.addStretch()
        main_v_layout.addLayout(layout)
        main_v_layout.addStretch()

>>>>>>> 8442dde4573edfc7ce551e9a80d91eb57b95dce0
        self.id_input.returnPressed.connect(self.validate_login)
        self.pw_input.returnPressed.connect(self.validate_login)
        self.login_btn.clicked.connect(self.validate_login)

    def validate_login(self):
        user_id = self.id_input.text().strip()
        user_pw = self.pw_input.text().strip()

        if user_id == "admin" and user_pw == "1234":
            # 0번 인덱스(Debug)면 True, 아니면 False 전송
            is_debug = (self.mode_selector.currentIndex() == 0)
            self.login_success.emit(is_debug)
        else:
            self.id_input.setStyleSheet(self.error_style)
            self.pw_input.setStyleSheet(self.error_style)
            self.pw_input.clear()
            self.pw_input.setPlaceholderText("비밀번호가 틀렸습니다")
