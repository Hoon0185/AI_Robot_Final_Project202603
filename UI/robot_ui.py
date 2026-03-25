import cv2
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QSlider, QFrame, QStackedWidget, QGridLayout)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

os.environ["OPENCV_LOG_LEVEL"] = "SILENT"

class RobotControlPanel(QWidget):
    # --- [LOGIC SIGNALS] ---

    # 순찰 시간 설정(분)
    patrolTimeConfirmed = pyqtSignal(int)
    # 장애물 인식 시간(초)
    obstacleConfirmed = pyqtSignal(int)
    # 상/하/좌/우/정지 명령 전달
    moveCommand = pyqtSignal(str)
    # 부저 울리기 버튼 클릭
    buzzerClicked = pyqtSignal()
    # 순찰 복귀 버튼 클릭
    returnClicked = pyqtSignal()
    # 비상 정지 버튼 클릭
    emergencyClicked = pyqtSignal()
    # 초기 위치 복귀 팝업에서 "예" 클릭 시 발생
    resetConfirmed = pyqtSignal()

    # --------------------------------

    def __init__(self):
        super().__init__()
        self._init_styles() # QSS 스타일 정의 로드
        self.initUI() # 전체 레이아웃 구성
        self._init_timers() # 카메라 영상 갱신을 위한 타이머 설정
        self._connect_internal_events() # UI 내부 버튼 클릭 시 시그널 발생

    # UI에 적용할 CSS 스타일 Init
    def _init_styles(self):
        self.main_qss = "background-color: #F0F4F8; font-family: 'Malgun Gothic';"
        # 기본 버튼 스타일 (호버 배경색 + 클릭 시 텍스트 이동 효과 포함)
        self.base_btn_qss = """
            QPushButton { color: #333; font-size: 16px; font-weight: bold; border-radius: 12px; %s }
            QPushButton:hover { background-color: %s; }
            QPushButton:pressed { padding-top: 5px; padding-left: 5px; }
        """
        self.slider_qss = """
            QSlider::groove:horizontal { background: #E0E0E0; height: 8px; border-radius: 4px; }
            QSlider::sub-page:horizontal { background: #28A745; height: 8px; border-radius: 4px; }
            QSlider::handle:horizontal { background: #E86464; width: 18px; height: 18px; margin: -5px 0; border-radius: 9px; }
        """

    # 메인 레이아웃 및 구성 요소 배치
    def initUI(self):
        self.setWindowTitle("Robot Management System")
        self.setGeometry(100, 100, 1200, 850)
        self.setStyleSheet(self.main_qss)
        self.container_layout = QGridLayout(self)
        self.container_layout.setContentsMargins(0, 0, 0, 0)

        self.main_window = QWidget()
        self.main_layout = QHBoxLayout(self.main_window)
        self.main_layout.setContentsMargins(25, 25, 25, 25)
        self.main_layout.setSpacing(30)

        self._setup_left_panel()
        self._setup_right_panel()
        self._setup_popups()

        self.container_layout.addWidget(self.main_window, 0, 0)
        self.container_layout.addWidget(self.overlay, 0, 0)
        self.container_layout.addWidget(self.map_overlay, 0, 0)

    # 왼쪽 패널 구성 : 캠 영상, 로그 시간, 슬라이더들
    def _setup_left_panel(self):
        left_container = QVBoxLayout()
        self.cam_label = QLabel("캠 영상 송출")
        self.cam_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam_label.setStyleSheet("background-color: #2C2C2C; color: white; border-radius: 15px; font-size: 18px; font-weight: bold;")
        self.cam_label.setMinimumHeight(450)
        left_container.addWidget(self.cam_label, stretch=3)

        logs_frame = QFrame()
        logs_frame.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #D1D9E6;")
        logs_layout = QHBoxLayout(logs_frame)
        logs_layout.addWidget(QLabel("  🗓  마지막 순찰 시간  "))
        self.logs_time = QLabel("2026:03:24:11:20:00")
        self.logs_time.setStyleSheet("background-color: #F0F4F8; padding: 8px; border-radius: 5px;")
        logs_layout.addStretch(); logs_layout.addWidget(self.logs_time)
        left_container.addWidget(logs_frame)

        settings_frame = QFrame()
        settings_frame.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #D1D9E6;")
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.addWidget(QLabel("PATROL & OBSTACLE SETTINGS"))

        self.patrol_row = self._create_slider_row("순찰 시간 조절", 60, "(분)")
        self.obstacle_row = self._create_slider_row("장애물 인식 조절", 10, "(초)")
        settings_layout.addWidget(self.patrol_row['frame'])
        settings_layout.addWidget(self.obstacle_row['frame'])
        left_container.addWidget(settings_frame)
        self.main_layout.addLayout(left_container, 1)

    # 왼쪽 패널의 슬라이더 구성(슬라이더+라벨+버튼)
    def _create_slider_row(self, label_text, default_val, unit):
        row_frame = QFrame()
        row_frame.setStyleSheet("QFrame { border: 1px solid #DDE4ED; border-radius: 15px; background: white; }")
        row = QHBoxLayout(row_frame); row.setContentsMargins(10, 5, 10, 5)
        lbl = QLabel(label_text); lbl.setFixedWidth(120)
        lbl.setStyleSheet("border: 1px solid #DDE4ED; border-radius: 10px; padding: 5px; background: white;")
        slider = QSlider(Qt.Orientation.Horizontal); slider.setRange(0, 100); slider.setValue(default_val)
        slider.setStyleSheet(self.slider_qss)
        val_lbl = QLabel(f"{default_val}{unit}"); val_lbl.setFixedWidth(65); val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_lbl.setStyleSheet("border: 1px solid #DDE4ED; border-radius: 10px; padding: 5px; background: white;")
        btn = QPushButton("확인"); btn.setFixedSize(60, 32)
        # 확인 버튼도 클릭 효과 추가
        btn.setStyleSheet("QPushButton { border: 2px solid #28A745; color: #28A745; border-radius: 8px; background: white; font-weight: bold; } QPushButton:hover { background-color: #EAF7ED; } QPushButton:pressed { padding-top: 2px; padding-left: 2px; background-color: #D4EDDA; }")
        row.addWidget(lbl); row.addWidget(slider); row.addWidget(val_lbl); row.addWidget(btn)
        slider.valueChanged.connect(lambda v: val_lbl.setText(f"{v}{unit}"))
        return {'frame': row_frame, 'slider': slider, 'btn': btn}

    # 오른쪽 패널 구성: 핵심 기능 버튼 5개와 로고용 레이아웃 공간 배치
    def _setup_right_panel(self):
        self.right_stack = QStackedWidget()
        self.page_main = QWidget()
        layout = QVBoxLayout(self.page_main); layout.setContentsMargins(0, 0, 0, 0)

        # 메인 버튼들 (클릭 효과 적용됨)
        self.btn_alarm = QPushButton("🔔 재고 알림 버튼")
        self.btn_alarm.setStyleSheet(self.base_btn_qss % ("border: 2px solid #E86464; background-color: #E86464; color: white;", "#D55555"))
        self.btn_db = QPushButton("🗄 DB 조회 버튼")
        self.btn_db.setStyleSheet(self.base_btn_qss % ("border: 2px solid #AED9FF; background-color: #AED9FF;", "#95C4EE"))
        self.btn_manual = QPushButton("🕹 수동 조작 버튼")
        self.btn_manual.setStyleSheet(self.base_btn_qss % ("border: 2px solid #28A745; background-color: #FFFFFF;", "#F5F5F5"))
        self.btn_reset = QPushButton("🔄 초기 위치 버튼")
        self.btn_reset.setStyleSheet(self.base_btn_qss % ("border: 2px solid #789D9E; background-color: #789D9E; color: white;", "#668B8C"))

        for btn in [self.btn_alarm, self.btn_db, self.btn_manual, self.btn_reset]:
            btn.setFixedHeight(85); layout.addWidget(btn); layout.addSpacing(12)

        self.map_btn = QPushButton("🗺 맵 버튼\nView Full Map")
        self.map_btn.setStyleSheet("QPushButton { background-color: white; border: 2px solid #0056b3; color: #333; font-size: 16px; font-weight: bold; border-radius: 12px; } QPushButton:hover { background-color: #E8F0FE; } QPushButton:pressed { padding-top: 5px; padding-left: 5px; background-color: #D2E3FC; }")
        self.map_btn.setFixedHeight(85); layout.addWidget(self.map_btn)

        layout.addSpacing(25)
        self.logo_area = QFrame(); self.logo_area.setStyleSheet("QFrame { background-color: white; border: 2px dashed #D1D9E6; border-radius: 15px; }")
        logo_label = QLabel("LOGO HERE"); logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter); QVBoxLayout(self.logo_area).addWidget(logo_label)
        layout.addWidget(self.logo_area, stretch=2)

        self._setup_remote_page()
        self.right_stack.addWidget(self.page_main); self.right_stack.addWidget(self.page_remote)
        self.main_layout.addWidget(self.right_stack, 1)

    def _setup_remote_page(self):
        self.page_remote = QWidget()
        layout = QVBoxLayout(self.page_remote); layout.setContentsMargins(0, 0, 0, 0)
        remote_frame = QFrame()
        remote_frame.setStyleSheet("QFrame { background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #E3E9F0, stop:1 #FFFFFF); border-radius: 20px; border: 1px solid #CFD8E3; }")
        inner = QVBoxLayout(remote_frame); inner.setContentsMargins(25, 30, 25, 30)

        title = QLabel("🕹 수동 조작 모드"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); title.setStyleSheet("font-size: 24px; font-weight: 900; color: #2C3E50; border: none; background: transparent;")
        inner.addWidget(title); inner.addStretch(1)

        # 방향키 그리드 (클릭 시 텍스트 이동 효과 포함)
        nav_card = QFrame(); nav_card.setStyleSheet("background: rgba(255, 255, 255, 0.5); border-radius: 20px; border: 1px solid #DDE4ED;")
        nav_grid = QGridLayout(nav_card)
        nav_style = "QPushButton { background-color: white; border: 2px solid #28A745; border-radius: 25px; font-size: 32px; min-height: 100px; min-width: 80px; color: #28A745; } QPushButton:hover { background-color: #EAF7ED; } QPushButton:pressed { padding-top: 8px; padding-left: 8px; background-color: #D4EDDA; }"

        self.btn_up = QPushButton("▲"); self.btn_up.setStyleSheet(nav_style)
        self.btn_down = QPushButton("▼"); self.btn_down.setStyleSheet(nav_style)
        self.btn_left = QPushButton("◀"); self.btn_left.setStyleSheet(nav_style)
        self.btn_right = QPushButton("▶"); self.btn_right.setStyleSheet(nav_style)
        self.btn_stop = QPushButton("정지"); self.btn_stop.setStyleSheet(nav_style.replace("#28A745", "#5A6268").replace("32px", "22px"))

        nav_grid.addWidget(self.btn_up, 0, 1); nav_grid.addWidget(self.btn_left, 1, 0); nav_grid.addWidget(self.btn_stop, 1, 1); nav_grid.addWidget(self.btn_right, 1, 2); nav_grid.addWidget(self.btn_down, 2, 1)
        inner.addWidget(nav_card); inner.addStretch(1)

        # --- [핵심 수정] 하단 특수 버튼 3개 효과 원본 동일 복구 ---
        extra_h_box = QHBoxLayout()
        # 원본의 QPushButton:pressed { padding: 5px; } 효과 적용
        ex_style = """
            QPushButton { background-color: white; border-radius: 15px; font-weight: bold; min-height: 85px; font-size: 16px; border: 2px solid %s; color: %s; }
            QPushButton:hover { background-color: %s; }
            QPushButton:pressed { padding-top: 5px; padding-left: 5px; }
        """
        self.btn_buzzer = QPushButton("🔊\n부저"); self.btn_buzzer.setStyleSheet(ex_style % ("#789D9E", "#4A6E6F", "#F0F7F7"))
        self.btn_return = QPushButton("🔄\n순찰복귀"); self.btn_return.setStyleSheet(ex_style % ("#789D9E", "#4A6E6F", "#F0F7F7"))
        self.btn_emerg = QPushButton("🚨\n비상정지"); self.btn_emerg.setStyleSheet(ex_style % ("#E86464", "#C0392B", "#FFF5F5"))

        extra_h_box.addWidget(self.btn_buzzer); extra_h_box.addWidget(self.btn_return); extra_h_box.addWidget(self.btn_emerg)
        inner.addLayout(extra_h_box); inner.addStretch(2)

        self.btn_back = QPushButton("◀ 메인 화면으로 돌아가기")
        self.btn_back.setFixedHeight(65)
        self.btn_back.setStyleSheet("QPushButton { background-color: #333; color: white; border-radius: 15px; font-weight: bold; } QPushButton:hover { background-color: #555; } QPushButton:pressed { padding-top: 5px; padding-left: 5px; }")
        inner.addWidget(self.btn_back); layout.addWidget(remote_frame)

    def _setup_popups(self):
        # 팝업 예/아니오 버튼 효과도 복구
        self.overlay = QFrame(); self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 120);"); self.overlay.hide()
        self.popup_box = QFrame(self.overlay); self.popup_box.setFixedSize(520, 320); self.popup_box.setStyleSheet("background-color: white; border-radius: 25px; border: 3px solid #DDE4ED;")
        p_layout = QVBoxLayout(self.popup_box); p_layout.setContentsMargins(35, 40, 35, 40)

        p_title = QLabel("로봇의 처음 위치로\n돌아가시겠습니까?"); p_title.setAlignment(Qt.AlignmentFlag.AlignCenter); p_title.setStyleSheet("font-size: 26px; font-weight: 900; color: #2C3E50; border: none;")
        p_desc = QLabel("확인을 누르면 로봇이 즉시 처음 설정된 시작 지점으로 이동합니다."); p_desc.setAlignment(Qt.AlignmentFlag.AlignCenter); p_desc.setStyleSheet("font-size: 14px; color: #7F8C8D; border: none;"); p_desc.setWordWrap(True)

        btn_row = QHBoxLayout(); btn_row.setSpacing(20)
        self.btn_yes = QPushButton("↩ 예"); self.btn_yes.setFixedHeight(65)
        self.btn_yes.setStyleSheet("QPushButton { background-color: #28A745; color: white; border-radius: 18px; font-size: 20px; font-weight: bold; } QPushButton:hover { background-color: #218838; } QPushButton:pressed { padding-top: 5px; padding-left: 5px; }")
        self.btn_no = QPushButton("아니오 ⚓"); self.btn_no.setFixedHeight(65)
        self.btn_no.setStyleSheet("QPushButton { background-color: #E86464; color: white; border-radius: 18px; font-size: 20px; font-weight: bold; } QPushButton:hover { background-color: #C0392B; } QPushButton:pressed { padding-top: 5px; padding-left: 5px; }")

        btn_row.addWidget(self.btn_yes); btn_row.addWidget(self.btn_no); p_layout.addWidget(p_title); p_layout.addWidget(p_desc); p_layout.addStretch(); p_layout.addLayout(btn_row)

        # 맵 팝업 닫기 버튼 효과 복구
        self.map_overlay = QFrame(); self.map_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 150);"); self.map_overlay.hide()
        self.map_popup_box = QFrame(self.map_overlay); self.map_popup_box.setFixedSize(850, 700); self.map_popup_box.setStyleSheet("background-color: white; border-radius: 30px;")
        m_layout = QVBoxLayout(self.map_popup_box); m_layout.setContentsMargins(30, 30, 30, 30)
        m_title = QLabel("로봇 실시간 위치"); m_title.setAlignment(Qt.AlignmentFlag.AlignCenter); m_title.setStyleSheet("font-size: 26px; font-weight: 900; color: #2C3E50;")
        self.map_area = QFrame(); self.map_area.setStyleSheet("background-color: #F8F9FA; border: 1px solid #DDE4ED; border-radius: 15px;")
        map_placeholder = QLabel("MAP GRID AREA"); map_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter); QVBoxLayout(self.map_area).addWidget(map_placeholder)
        self.btn_map_close = QPushButton("닫기"); self.btn_map_close.setFixedHeight(65)
        self.btn_map_close.setStyleSheet("QPushButton { background-color: #28A745; color: white; border-radius: 18px; font-size: 22px; font-weight: bold; } QPushButton:hover { background-color: #218838; } QPushButton:pressed { padding-top: 5px; padding-left: 5px; }")
        m_layout.addWidget(m_title); m_layout.addWidget(self.map_area, stretch=1); m_layout.addSpacing(20); m_layout.addWidget(self.btn_map_close)

    def _connect_internal_events(self):
        self.btn_manual.clicked.connect(lambda: self.right_stack.setCurrentIndex(1))
        self.btn_back.clicked.connect(lambda: self.right_stack.setCurrentIndex(0))
        self.btn_reset.clicked.connect(self.open_popup)
        self.btn_no.clicked.connect(self.close_popup)
        self.btn_yes.clicked.connect(self.close_popup)
        self.map_btn.clicked.connect(self.open_map)
        self.btn_map_close.clicked.connect(self.close_map)
        self.patrol_row['btn'].clicked.connect(lambda: self.patrolTimeConfirmed.emit(self.patrol_row['slider'].value()))
        self.obstacle_row['btn'].clicked.connect(lambda: self.obstacleConfirmed.emit(self.obstacle_row['slider'].value()))
        self.btn_yes.clicked.connect(self.resetConfirmed.emit)
        self.btn_up.clicked.connect(lambda: self.moveCommand.emit("UP"))
        self.btn_down.clicked.connect(lambda: self.moveCommand.emit("DOWN"))
        self.btn_left.clicked.connect(lambda: self.moveCommand.emit("LEFT"))
        self.btn_right.clicked.connect(lambda: self.moveCommand.emit("RIGHT"))
        self.btn_stop.clicked.connect(lambda: self.moveCommand.emit("STOP"))
        self.btn_buzzer.clicked.connect(self.buzzerClicked.emit)
        self.btn_return.clicked.connect(self.returnClicked.emit)
        self.btn_emerg.clicked.connect(self.emergencyClicked.emit)

    def _init_timers(self):
        self.timer = QTimer(); self.timer.timeout.connect(self.update_frame)
        self.cap = cv2.VideoCapture(0); self.timer.start(30)

    def update_frame(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1); rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                qt_image = QImage(rgb_image.data, rgb_image.shape[1], rgb_image.shape[0], rgb_image.shape[1]*3, QImage.Format.Format_RGB888)
                self.cam_label.setPixmap(QPixmap.fromImage(qt_image).scaled(self.cam_label.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))

    def open_popup(self): self.overlay.show(); self.center_popup(self.popup_box)
    def close_popup(self): self.overlay.hide()
    def open_map(self): self.map_overlay.show(); self.center_popup(self.map_popup_box)
    def close_map(self): self.map_overlay.hide()
    def center_popup(self, box):
        qr = box.frameGeometry(); cp = self.rect().center(); qr.moveCenter(cp); box.move(qr.topLeft())
    def resizeEvent(self, event):
        if self.overlay.isVisible(): self.center_popup(self.popup_box)
        if self.map_overlay.isVisible(): self.center_popup(self.map_popup_box)
        super().resizeEvent(event)
