import sys
import cv2
import os
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QSlider, QFrame)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap

# OpenCV 터미널 에러 메시지 억제
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"

class RobotControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        # 카메라 연결 시도
        self.cap = cv2.VideoCapture(0)
        self.timer.start(30)

    def initUI(self):
        self.setWindowTitle("Robot Management System")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("background-color: #F0F4F8; font-family: 'Malgun Gothic';")

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(30)

        left_container = QVBoxLayout()
        right_container = QVBoxLayout() # 우측 전체를 담는 메인 세로 레이아웃

        # --- 왼쪽 영역 (Left) ---
        self.cam_label = QLabel("캠 영상 송출")
        self.cam_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam_label.setStyleSheet("""
            background-color: #2C2C2C; color: white; border-radius: 15px;
            font-size: 18px; font-weight: bold;
        """)
        self.cam_label.setMinimumHeight(400)
        left_container.addWidget(self.cam_label, stretch=2)

        # LOGS 섹션
        logs_frame = QFrame()
        logs_frame.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #D1D9E6;")
        logs_layout = QHBoxLayout(logs_frame)
        logs_layout.addWidget(QLabel("🗓 LOGS  마지막 순찰 시간"))

        logs_time = QLabel("2026:03:24:11:20:00")
        logs_time.setStyleSheet("background-color: #F0F4F8; padding: 8px; border-radius: 5px;")

        logs_layout.addStretch()
        logs_layout.addWidget(logs_time)
        left_container.addWidget(logs_frame)

        # Settings 섹션
        settings_frame = QFrame()
        settings_frame.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #D1D9E6;")
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.addWidget(QLabel("PATROL & OBSTACLE SETTINGS"))

        def create_slider_row(label_text, default_val, unit):
            row_widget = QWidget()
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 5, 0, 5)

            lbl = QLabel(label_text)
            lbl.setFixedWidth(140)
            row.addWidget(lbl)

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setStyleSheet("""
                QSlider::groove:horizontal { background: #E0E0E0; height: 6px; border-radius: 3px; }
                QSlider::handle:horizontal { background: #E86464; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }
            """)
            row.addWidget(slider)

            val_lbl = QLabel(f"{default_val}{unit}")
            val_lbl.setFixedWidth(60)
            row.addWidget(val_lbl)

            btn = QPushButton("확인")
            btn.setFixedSize(60, 30)
            btn.setStyleSheet("""
                QPushButton { border: 1px solid #28A745; color: #28A745; border-radius: 5px; background: white; font-weight: bold; }
                QPushButton:hover { background: #F1F9F3; }
                QPushButton:pressed { background: #E2F2E7; padding-top: 2px; }
            """)
            row.addWidget(btn)
            return row_widget

        settings_layout.addWidget(create_slider_row("순찰 시간 조절", 60, "(분)"))
        settings_layout.addWidget(create_slider_row("장애물 인식 조절", 10, "(초)"))
        left_container.addWidget(settings_frame)

        # --- 오른쪽 영역 (Right) ---
        # 상단 버튼들이 들어갈 서브 레이아웃
        button_layout = QVBoxLayout()

        base_btn_qss = "QPushButton { color: #333; font-size: 16px; font-weight: bold; border-radius: 10px; %s } " \
                       "QPushButton:hover { background-color: %s; } " \
                       "QPushButton:pressed { padding-top: 5px; padding-left: 2px; }"

        buttons_info = [
            ("🔔 재고 알림 버튼", "#E86464", "#D55555"),
            ("🗄 DB 조회 버튼", "#AED9FF", "#95C4EE"),
            ("🕹 수동 조작 버튼", "#FFFFFF", "#F5F5F5"),
            ("🔄 초기 위치 버튼", "#789D9E", "#668B8C"),
        ]

        for text, color, hover_color in buttons_info:
            btn = QPushButton(text)
            border_color = color if color != '#FFFFFF' else '#28A745'
            border_style = f"border: 2px solid {border_color}; background-color: {color};"

            btn.setStyleSheet(base_btn_qss % (border_style, hover_color))
            btn.setFixedHeight(80)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            button_layout.addWidget(btn)
            button_layout.addSpacing(10)

        # 맵 버튼
        map_btn = QPushButton("🗺 맵 버튼\nView Full Map")
        map_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 2px solid #0056b3;
                color: #333;
                font-size: 16px;
                font-weight: bold;
                border-radius: 10px;
            }
            QPushButton:hover { background-color: #F0F7FF; }
            QPushButton:pressed { padding-top: 5px; padding-left: 2px; }
        """)
        map_btn.setFixedHeight(80)
        map_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_layout.addWidget(map_btn)

        # 버튼들을 위로 밀어주는 장치
        right_container.addLayout(button_layout)
        right_container.addSpacing(20) # 버튼 영역과 로고 영역 사이 간격

        # --- 우하단 로고 추가 영역 ---
        self.logo_area = QFrame()
        self.logo_area.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px dashed #D1D9E6; /* 영역 구분을 위한 점선 */
                border-radius: 15px;
            }
        """)
        # 로고 텍스트 혹은 이미지가 들어갈 라벨
        logo_label = QLabel("LOGO HERE")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("color: #ABB2B9; font-size: 20px; font-weight: bold; border: none;")

        logo_layout = QVBoxLayout(self.logo_area)
        logo_layout.addWidget(logo_label)

        # 로고 영역을 우하단에 배치 (stretch를 주어 남은 공간을 차지하게 함)
        right_container.addWidget(self.logo_area, stretch=1)

        # 레이아웃 최종 합체
        main_layout.addLayout(left_container, 1)
        main_layout.addLayout(right_container, 1)
        self.setLayout(main_layout)

    def update_frame(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                self.cam_label.setPixmap(QPixmap.fromImage(qt_image).scaled(
                    self.cam_label.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))

    def closeEvent(self, event):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = RobotControlPanel()
    ex.show()
    sys.exit(app.exec())
