import sys
import cv2
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QSlider, QFrame)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap

class RobotControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.cap = cv2.VideoCapture(0)
        self.timer.start(30)

    def initUI(self):
        self.setWindowTitle("Robot Management System")
        self.setGeometry(100, 100, 1200, 800) # 가로를 조금 더 여유있게 설정
        self.setStyleSheet("background-color: #F0F4F8; font-family: 'Malgun Gothic';")

        # 메인 레이아웃 (좌:우 비율 1:1)
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(30)

        left_container = QVBoxLayout()
        right_container = QVBoxLayout()

        # --- 왼쪽 영역 (Left) ---
        # 1. 캠 영상 (정사각형에 가깝게 비율 조정)
        self.cam_label = QLabel("캠 영상 송출")
        self.cam_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam_label.setStyleSheet("""
            background-color: #2C2C2C; color: white; border-radius: 15px;
            font-size: 18px; font-weight: bold;
        """)
        self.cam_label.setMinimumHeight(400)
        left_container.addWidget(self.cam_label, stretch=2) # 영상 영역 비중 높임

        # 2. LOGS 섹션
        logs_frame = QFrame()
        logs_frame.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #D1D9E6;")
        logs_layout = QHBoxLayout(logs_frame)
        logs_layout.addWidget(QLabel("🗓 LOGS  마지막 순찰 시간"))
        logs_time = QLabel("2026:03:24:11:20:00")
        logs_time.setStyleSheet("background-color: #F0F4F8; padding: 8px; border-radius: 5px;")
        logs_layout.addStretch()
        logs_layout.addWidget(logs_time)
        left_container.addWidget(logs_frame)

        # 3. Settings 섹션
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
                QSlider::handle:horizontal { background: #E86464; border-radius: 5px; width: 15px; }
            """)
            row.addWidget(slider)

            val_lbl = QLabel(f"{default_val}{unit}")
            val_lbl.setFixedWidth(60)
            row.addWidget(val_lbl)

            btn = QPushButton("확인")
            btn.setFixedSize(60, 30)
            btn.setStyleSheet("border: 1px solid #28A745; color: #28A745; border-radius: 5px; background: white;")
            row.addWidget(btn)
            return row_widget

        settings_layout.addWidget(create_slider_row("순찰 시간 조절", 60, "(분)"))
        settings_layout.addWidget(create_slider_row("장애물 인식 조절", 10, "(초)"))
        left_container.addWidget(settings_frame)

        # --- 오른쪽 영역 (Right) ---
        # 버튼들 간의 간격을 일정하게 유지하기 위해 stretch 활용
        btn_style = "color: #333; font-size: 16px; font-weight: bold; border-radius: 10px;"

        buttons_info = [
            ("🔔 재고 알림 버튼", "#E86464"),
            ("🗄 DB 조회 버튼", "#AED9FF"),
            ("🕹 수동 조작 버튼", "#FFFFFF"),
            ("🔄 초기 위치 버튼", "#789D9E"),
        ]

        for text, color in buttons_info:
            btn = QPushButton(text)
            border_style = f"border: 2px solid {color if color != '#FFFFFF' else '#28A745'};"
            btn.setStyleSheet(f"{btn_style} background-color: {color}; {border_style}")
            btn.setFixedHeight(80) # 버튼 높이 고정
            right_container.addWidget(btn)
            right_container.addSpacing(10)

        # 맵 버튼 (하단에 배치, 남은 공간 차지)
        map_btn = QPushButton("🗺 맵 버튼\nView Full Map")
        map_btn.setStyleSheet(btn_style + "background-color: white; border: 2px solid #0056b3;")
        right_container.addWidget(map_btn, stretch=1)

        # 핵심 수정 사항: 좌/우 레이아웃을 1:1 비율로 추가
        main_layout.addLayout(left_container, 1)
        main_layout.addLayout(right_container, 1)

        self.setLayout(main_layout)

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, 1)
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            # label 크기에 맞춰 영상 출력
            pixmap = QPixmap.fromImage(qt_image)
            self.cam_label.setPixmap(pixmap.scaled(self.cam_label.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))

    def closeEvent(self, event):
        self.cap.release()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = RobotControlPanel()
    ex.show()
    sys.exit(app.exec())
