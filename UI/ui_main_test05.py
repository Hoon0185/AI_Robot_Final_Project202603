import sys
import cv2
import os
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QSlider, QFrame, QStackedWidget, QGridLayout)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap

os.environ["OPENCV_LOG_LEVEL"] = "SILENT"

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
        self.setGeometry(100, 100, 1200, 850)
        self.setStyleSheet("background-color: #F0F4F8; font-family: 'Malgun Gothic';")

        # 최상위 그리드 레이아웃 (메인 UI와 팝업 오버레이를 겹치기 위함)
        self.container_layout = QGridLayout(self)
        self.container_layout.setContentsMargins(0, 0, 0, 0)

        # ================= [ 1. 메인 UI 전체 위젯 ] =================
        self.main_window = QWidget()
        main_layout = QHBoxLayout(self.main_window)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(30)

        # --- [왼쪽 컨테이너] ---
        left_container = QVBoxLayout()
        self.cam_label = QLabel("캠 영상 송출")
        self.cam_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam_label.setStyleSheet("background-color: #2C2C2C; color: white; border-radius: 15px; font-size: 18px; font-weight: bold;")
        self.cam_label.setMinimumHeight(450)
        left_container.addWidget(self.cam_label, stretch=3)

        logs_frame = QFrame()
        logs_frame.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #D1D9E6;")
        logs_layout = QHBoxLayout(logs_frame)
        logs_layout.addWidget(QLabel("🗓 LOGS  마지막 순찰 시간"))
        logs_time = QLabel("2026:03:24:11:20:00")
        logs_time.setStyleSheet("background-color: #F0F4F8; padding: 8px; border-radius: 5px;")
        logs_layout.addStretch(); logs_layout.addWidget(logs_time)
        left_container.addWidget(logs_frame)

        # 설정 영역
        settings_frame = QFrame()
        settings_frame.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #D1D9E6;")
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.addWidget(QLabel("PATROL & OBSTACLE SETTINGS"))

        def create_slider_row(label_text, default_val, unit):
            row_widget = QWidget(); row = QHBoxLayout(row_widget); row.setContentsMargins(0, 5, 0, 5)
            lbl = QLabel(label_text); lbl.setFixedWidth(140); row.addWidget(lbl)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setStyleSheet("QSlider::groove:horizontal { background: #E0E0E0; height: 6px; border-radius: 3px; } QSlider::handle:horizontal { background: #E86464; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }")
            row.addWidget(slider)
            val_lbl = QLabel(f"{default_val}{unit}"); val_lbl.setFixedWidth(60); row.addWidget(val_lbl)
            btn = QPushButton("확인"); btn.setFixedSize(60, 30); btn.setStyleSheet("QPushButton { border: 1px solid #28A745; color: #28A745; border-radius: 5px; background: white; font-weight: bold; }")
            row.addWidget(btn)
            return row_widget

        settings_layout.addWidget(create_slider_row("순찰 시간 조절", 60, "(분)"))
        settings_layout.addWidget(create_slider_row("장애물 인식 조절", 10, "(초)"))
        left_container.addWidget(settings_frame)

        # --- [오른쪽 컨테이너 (StackedWidget)] ---
        self.right_stack = QStackedWidget()

        # --- Page 1: 메인 메뉴 ---
        self.page_main = QWidget()
        page_main_layout = QVBoxLayout(self.page_main)
        page_main_layout.setContentsMargins(0, 0, 0, 0)

        base_btn_qss = "QPushButton { color: #333; font-size: 16px; font-weight: bold; border-radius: 12px; %s } QPushButton:hover { background-color: %s; } QPushButton:pressed { padding-top: 5px; padding-left: 5px; }"

        self.btn_alarm = QPushButton("🔔 재고 알림 버튼")
        self.btn_alarm.setStyleSheet(base_btn_qss % ("border: 2px solid #E86464; background-color: #E86464;", "#D55555"))
        self.btn_db = QPushButton("🗄 DB 조회 버튼")
        self.btn_db.setStyleSheet(base_btn_qss % ("border: 2px solid #AED9FF; background-color: #AED9FF;", "#95C4EE"))
        self.btn_manual = QPushButton("🕹 수동 조작 버튼")
        self.btn_manual.setStyleSheet(base_btn_qss % ("border: 2px solid #28A745; background-color: #FFFFFF;", "#F5F5F5"))
        self.btn_reset = QPushButton("🔄 초기 위치 버튼")
        self.btn_reset.setStyleSheet(base_btn_qss % ("border: 2px solid #789D9E; background-color: #789D9E;", "#668B8C"))

        for btn in [self.btn_alarm, self.btn_db, self.btn_manual, self.btn_reset]:
            btn.setFixedHeight(85); page_main_layout.addWidget(btn); page_main_layout.addSpacing(12)

        map_btn = QPushButton("🗺 맵 버튼\nView Full Map")
        map_btn.setStyleSheet("QPushButton { background-color: white; border: 2px solid #0056b3; color: #333; font-size: 16px; font-weight: bold; border-radius: 12px; }")
        map_btn.setFixedHeight(85); page_main_layout.addWidget(map_btn)

        page_main_layout.addSpacing(25)
        self.logo_area = QFrame()
        self.logo_area.setStyleSheet("QFrame { background-color: white; border: 2px dashed #D1D9E6; border-radius: 15px; }")
        logo_label = QLabel("LOGO HERE"); logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        QVBoxLayout(self.logo_area).addWidget(logo_label)
        page_main_layout.addWidget(self.logo_area, stretch=2)

        # --- Page 2: 수동 조작 리모컨 ---
        self.page_remote = QWidget()
        page_remote_layout = QVBoxLayout(self.page_remote)
        page_remote_layout.setContentsMargins(0, 0, 0, 0)

        remote_frame = QFrame()
        remote_frame.setStyleSheet("QFrame { background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #E3E9F0, stop:1 #FFFFFF); border-radius: 20px; border: 1px solid #CFD8E3; }")
        remote_inner = QVBoxLayout(remote_frame)
        remote_inner.setContentsMargins(25, 30, 25, 30)

        title = QLabel("🕹 수동 조작 모드")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: 900; color: #2C3E50; border: none; background: transparent;")
        remote_inner.addWidget(title); remote_inner.addStretch(1)

        # 방향키 카드 영역
        nav_card = QFrame()
        nav_card.setStyleSheet("background: rgba(255, 255, 255, 0.5); border-radius: 20px; border: 1px solid #DDE4ED;")
        nav_grid = QGridLayout(nav_card)
        nav_style = """
            QPushButton {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F1F3F5);
                border: 2px solid #28A745; border-radius: 25px;
                font-size: 32px; min-height: 100px; min-width: 80px; color: #28A745;
            }
            QPushButton:hover { background-color: #EAF7ED; }
            QPushButton:pressed { padding-top: 5px; padding-left: 5px; background-color: #D4EDDA; }
        """
        btn_up = QPushButton("▲"); btn_up.setStyleSheet(nav_style)
        btn_down = QPushButton("▼"); btn_down.setStyleSheet(nav_style)
        btn_left = QPushButton("◀"); btn_left.setStyleSheet(nav_style)
        btn_right = QPushButton("▶"); btn_right.setStyleSheet(nav_style)
        btn_stop = QPushButton("정지"); btn_stop.setStyleSheet(nav_style.replace("#28A745", "#5A6268").replace("32px", "22px"))

        nav_grid.addWidget(btn_up, 0, 1); nav_grid.addWidget(btn_left, 1, 0)
        nav_grid.addWidget(btn_stop, 1, 1); nav_grid.addWidget(btn_right, 1, 2); nav_grid.addWidget(btn_down, 2, 1)
        remote_inner.addWidget(nav_card); remote_inner.addStretch(1)

        # 추가 제어 버튼
        remote_inner.addWidget(QLabel("추가 제어 버튼 (Additional Controls)"))
        extra_h_box = QHBoxLayout()
        ex_style = "QPushButton { background-color: white; border-radius: 15px; font-weight: bold; min-height: 85px; font-size: 16px; border: 2px solid %s; color: %s; } QPushButton:hover { background-color: %s; } QPushButton:pressed { padding: 5px; background-color: %s; }"

        btn_buzzer = QPushButton("🔊\n부저"); btn_buzzer.setStyleSheet(ex_style % ("#789D9E", "#4A6E6F", "#F0F7F7", "#D1E3E4"))
        btn_return = QPushButton("🔄\n순찰복귀"); btn_return.setStyleSheet(ex_style % ("#789D9E", "#4A6E6F", "#F0F7F7", "#D1E3E4"))
        btn_emerg = QPushButton("🚨\n비상정지"); btn_emerg.setStyleSheet(ex_style % ("#E86464", "#C0392B", "#FFF5F5", "#FADBD8"))

        extra_h_box.addWidget(btn_buzzer); extra_h_box.addWidget(btn_return); extra_h_box.addWidget(btn_emerg)
        remote_inner.addLayout(extra_h_box); remote_inner.addStretch(2)

        self.btn_back = QPushButton("◀ 메인 화면으로 돌아가기")
        self.btn_back.setFixedHeight(65); self.btn_back.setStyleSheet("QPushButton { background-color: #333; color: white; border-radius: 15px; font-weight: bold; } QPushButton:pressed { padding: 5px; }")
        remote_inner.addWidget(self.btn_back)

        page_remote_layout.addWidget(remote_frame)
        self.right_stack.addWidget(self.page_main); self.right_stack.addWidget(self.page_remote)

        main_layout.addLayout(left_container, 1); main_layout.addWidget(self.right_stack, 1)

        # ================= [ 2. 팝업 오버레이 레이어 ] =================
        self.overlay = QFrame()
        self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 120);")
        self.overlay.hide()

        self.popup_box = QFrame(self.overlay) #
        self.popup_box.setFixedSize(520, 320)
        self.popup_box.setStyleSheet("background-color: white; border-radius: 25px; border: 3px solid #DDE4ED;")
        p_layout = QVBoxLayout(self.popup_box)
        p_layout.setContentsMargins(35, 40, 35, 40)

        p_title = QLabel("로봇의 처음 위치로\n돌아가시겠습니까?"); p_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_title.setStyleSheet("font-size: 26px; font-weight: 900; color: #2C3E50; border: none;")
        p_desc = QLabel("확인을 누르면 로봇이 즉시 처음 설정된 시작 지점으로 이동합니다."); p_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_desc.setStyleSheet("font-size: 14px; color: #7F8C8D; border: none;"); p_desc.setWordWrap(True)

        btn_row = QHBoxLayout(); btn_row.setSpacing(20)
        self.btn_yes = QPushButton("↩ 예"); self.btn_yes.setFixedHeight(65)
        self.btn_yes.setStyleSheet("QPushButton { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #28A745, stop:1 #1E7E34); color: white; border-radius: 18px; font-size: 20px; font-weight: bold; }")
        self.btn_no = QPushButton("아니오 ⚓"); self.btn_no.setFixedHeight(65)
        self.btn_no.setStyleSheet("QPushButton { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E86464, stop:1 #C0392B); color: white; border-radius: 18px; font-size: 20px; font-weight: bold; }")

        btn_row.addWidget(self.btn_yes); btn_row.addWidget(self.btn_no)
        p_layout.addWidget(p_title); p_layout.addWidget(p_desc); p_layout.addStretch(); p_layout.addLayout(btn_row)

        # 레이아웃 적층
        self.container_layout.addWidget(self.main_window, 0, 0)
        self.container_layout.addWidget(self.overlay, 0, 0)

        # 이벤트 연결
        self.btn_manual.clicked.connect(lambda: self.right_stack.setCurrentIndex(1))
        self.btn_back.clicked.connect(lambda: self.right_stack.setCurrentIndex(0))
        self.btn_reset.clicked.connect(self.open_popup)
        self.btn_no.clicked.connect(self.close_popup)
        self.btn_yes.clicked.connect(self.process_reset)

    def open_popup(self):
        self.overlay.show(); self.center_popup()

    def close_popup(self): self.overlay.hide()

    def process_reset(self): print("초기 위치 복귀 시작..."); self.close_popup()

    def center_popup(self):
        qr = self.popup_box.frameGeometry()
        cp = self.main_window.rect().center()
        qr.moveCenter(cp); self.popup_box.move(qr.topLeft())

    def resizeEvent(self, event):
        if self.overlay.isVisible(): self.center_popup()
        super().resizeEvent(event)

    def update_frame(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                qt_image = QImage(rgb_image.data, rgb_image.shape[1], rgb_image.shape[0], rgb_image.shape[1]*3, QImage.Format.Format_RGB888)
                self.cam_label.setPixmap(QPixmap.fromImage(qt_image).scaled(self.cam_label.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = RobotControlPanel()
    ex.show(); sys.exit(app.exec())
