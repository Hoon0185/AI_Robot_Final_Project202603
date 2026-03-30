import cv2
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QSlider, QFrame, QStackedWidget,
                             QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

os.environ["OPENCV_LOG_LEVEL"] = "SILENT"

class RobotControlPanel(QWidget):
    # --- [LOGIC SIGNALS] ---
    patrolTimeConfirmed = pyqtSignal(int)
    obstacleConfirmed = pyqtSignal(int)
    moveCommand = pyqtSignal(str)
    buzzerClicked = pyqtSignal()
    returnClicked = pyqtSignal()
    emergencyClicked = pyqtSignal()
    resetConfirmed = pyqtSignal()
    dbRefreshRequested = pyqtSignal()
    alarmRefreshRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._init_styles()
        self.initUI()
        self._init_timers()
        self._connect_internal_events()

    def _init_styles(self):
        self.main_qss = "background-color: #F0F4F8; font-family: 'Malgun Gothic';"
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
        self.container_layout.addWidget(self.db_overlay, 0, 0)
        self.container_layout.addWidget(self.alarm_overlay, 0, 0)

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

        # 마지막 순찰 시간 레이블 (초기값은 더미 데이터로 설정)
        self.logs_time = QLabel()
        self.set_last_patrol_time(None)

        self.logs_time.setStyleSheet("background-color: #F0F4F8; padding: 8px; border-radius: 5px;")
        logs_layout.addStretch(); logs_layout.addWidget(self.logs_time)
        left_container.addWidget(logs_frame)

        settings_frame = QFrame()
        settings_frame.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #D1D9E6;")
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.addWidget(QLabel("PATROL & OBSTACLE SETTINGS"))

        # 순찰 시간 조절: 최소 10, 최대 120
        self.patrol_row = self._create_slider_row("순찰 시간 조절", 60, "(분)", min_val=10, max_val=120)
        # 장애물 인식 조절: 최소 5, 최대 20
        self.obstacle_row = self._create_slider_row("장애물 인식 조절", 10, "(초)", min_val=5, max_val=20)

        settings_layout.addWidget(self.patrol_row['frame'])
        settings_layout.addWidget(self.obstacle_row['frame'])
        left_container.addWidget(settings_frame)
        self.main_layout.addLayout(left_container, 1)

    def _create_slider_row(self, label_text, default_val, unit, min_val=0, max_val=100):
        row_frame = QFrame()
        row_frame.setStyleSheet("QFrame { border: 1px solid #DDE4ED; border-radius: 15px; background: white; }")
        row = QHBoxLayout(row_frame); row.setContentsMargins(10, 5, 10, 5)
        lbl = QLabel(label_text); lbl.setFixedWidth(120)
        lbl.setStyleSheet("border: 1px solid #DDE4ED; border-radius: 10px; padding: 5px; background: white;")
        slider = QSlider(Qt.Orientation.Horizontal); slider.setRange(min_val, max_val); slider.setValue(default_val)
        slider.setStyleSheet(self.slider_qss)
        val_lbl = QLabel(f"{default_val}{unit}"); val_lbl.setFixedWidth(65); val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_lbl.setStyleSheet("border: 1px solid #DDE4ED; border-radius: 10px; padding: 5px; background: white;")
        btn = QPushButton("확인"); btn.setFixedSize(60, 32)
        btn.setStyleSheet("QPushButton { border: 2px solid #28A745; color: #28A745; border-radius: 8px; background: white; font-weight: bold; } QPushButton:hover { background-color: #EAF7ED; } QPushButton:pressed { padding-top: 2px; padding-left: 2px; background-color: #D4EDDA; }")
        row.addWidget(lbl); row.addWidget(slider); row.addWidget(val_lbl); row.addWidget(btn)
        slider.valueChanged.connect(lambda v: val_lbl.setText(f"{v}{unit}"))
        return {'frame': row_frame, 'slider': slider, 'btn': btn}

    def _setup_right_panel(self):
        self.right_stack = QStackedWidget()
        self.page_main = QWidget()
        layout = QVBoxLayout(self.page_main); layout.setContentsMargins(0, 0, 0, 0)

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
        self.right_stack.addWidget(self.page_main)   # Index 0
        self.right_stack.addWidget(self.page_remote) # Index 1
        self.main_layout.addWidget(self.right_stack, 1)

    def _setup_remote_page(self):
        self.page_remote = QWidget()
        layout = QVBoxLayout(self.page_remote); layout.setContentsMargins(0, 0, 0, 0)
        remote_frame = QFrame()
        remote_frame.setStyleSheet("QFrame { background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #E3E9F0, stop:1 #FFFFFF); border-radius: 20px; border: 1px solid #CFD8E3; }")
        inner = QVBoxLayout(remote_frame); inner.setContentsMargins(25, 30, 25, 30)
        title = QLabel("🕹 수동 조작 모드"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); title.setStyleSheet("font-size: 24px; font-weight: 900; color: #2C3E50; border: none; background: transparent;")
        inner.addWidget(title); inner.addStretch(1)

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

        extra_h_box = QHBoxLayout()
        ex_style = "QPushButton { background-color: white; border-radius: 15px; font-weight: bold; min-height: 85px; font-size: 16px; border: 2px solid %s; color: %s; } QPushButton:hover { background-color: %s; } QPushButton:pressed { padding-top: 5px; padding-left: 5px; }"
        self.btn_buzzer = QPushButton("🔊\n부저"); self.btn_buzzer.setStyleSheet(ex_style % ("#789D9E", "#4A6E6F", "#F0F7F7"))
        self.btn_return = QPushButton("🔄\n순찰복귀"); self.btn_return.setStyleSheet(ex_style % ("#789D9E", "#4A6E6F", "#F0F7F7"))
        self.btn_emerg = QPushButton("🚨\n비상정지"); self.btn_emerg.setStyleSheet(ex_style % ("#E86464", "#C0392B", "#FFF5F5"))
        extra_h_box.addWidget(self.btn_buzzer); extra_h_box.addWidget(self.btn_return); extra_h_box.addWidget(self.btn_emerg)
        inner.addLayout(extra_h_box); inner.addStretch(2)

        self.btn_back = QPushButton("◀ 메인 화면으로 돌아가기")
        self.btn_back.setFixedHeight(65); self.btn_back.setStyleSheet("QPushButton { background-color: #333; color: white; border-radius: 15px; font-weight: bold; } QPushButton:hover { background-color: #555; }")
        inner.addWidget(self.btn_back); layout.addWidget(remote_frame)

    def _setup_popups(self):
        # 1. 초기 위치 복귀 팝업
        self.overlay = QFrame(); self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 120);"); self.overlay.hide()
        self.popup_box = QFrame(self.overlay); self.popup_box.setFixedSize(520, 320); self.popup_box.setStyleSheet("background-color: white; border-radius: 25px; border: 3px solid #DDE4ED;")
        p_layout = QVBoxLayout(self.popup_box); p_layout.setContentsMargins(35, 40, 35, 40)
        p_title = QLabel("로봇의 처음 위치로\n돌아가시겠습니까?"); p_title.setAlignment(Qt.AlignmentFlag.AlignCenter); p_title.setStyleSheet("font-size: 26px; font-weight: 900; color: #2C3E50; border: none;")
        btn_row = QHBoxLayout(); btn_row.setSpacing(20)
        self.btn_yes = QPushButton("↩ 예"); self.btn_yes.setFixedHeight(65); self.btn_yes.setStyleSheet("QPushButton { background-color: #28A745; color: white; border-radius: 18px; font-size: 20px; font-weight: bold; }")
        self.btn_no = QPushButton("아니오 ⚓"); self.btn_no.setFixedHeight(65); self.btn_no.setStyleSheet("QPushButton { background-color: #E86464; color: white; border-radius: 18px; font-size: 20px; font-weight: bold; }")
        btn_row.addWidget(self.btn_yes); btn_row.addWidget(self.btn_no); p_layout.addWidget(p_title); p_layout.addStretch(); p_layout.addLayout(btn_row)

        # 2. 맵 팝업
        self.map_overlay = QFrame(); self.map_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 150);"); self.map_overlay.hide()
        self.map_popup_box = QFrame(self.map_overlay); self.map_popup_box.setFixedSize(850, 700); self.map_popup_box.setStyleSheet("background-color: white; border-radius: 30px;")
        m_layout = QVBoxLayout(self.map_popup_box); m_layout.setContentsMargins(30, 30, 30, 30)
        self.map_area = QFrame(); self.map_area.setStyleSheet("background-color: #F8F9FA; border: 1px solid #DDE4ED; border-radius: 15px;")
        self.btn_map_close = QPushButton("닫기"); self.btn_map_close.setFixedHeight(65); self.btn_map_close.setStyleSheet("QPushButton { background-color: #28A745; color: white; border-radius: 18px; font-size: 22px; font-weight: bold; }")
        m_layout.addWidget(QLabel("로봇 실시간 위치", alignment=Qt.AlignmentFlag.AlignCenter, styleSheet="font-size: 26px; font-weight: 900;")); m_layout.addWidget(self.map_area, stretch=1); m_layout.addSpacing(20); m_layout.addWidget(self.btn_map_close)

        # 3. DB 조회 팝업
        self.db_overlay = QFrame(); self.db_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 150);"); self.db_overlay.hide()
        self.db_popup_box = QFrame(self.db_overlay); self.db_popup_box.setFixedSize(1000, 750); self.db_popup_box.setStyleSheet("background-color: white; border-radius: 30px;")
        db_layout = QVBoxLayout(self.db_popup_box); db_layout.setContentsMargins(30, 30, 30, 30)
        self.db_table = QTableWidget(); self.db_table.setColumnCount(6)
        self.db_table.setHorizontalHeaderLabels(["카테고리", "제품이름", "제품번호(QR)", "기준 수량", "동기화 시각", "위치"])
        self.db_table.setStyleSheet("QHeaderView::section { background-color: #AED9FF; font-weight: bold; } QTableWidget { border-radius: 10px; }")
        self.db_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.btn_db_close = QPushButton("조회창 닫기"); self.btn_db_close.setFixedHeight(65); self.btn_db_close.setStyleSheet("QPushButton { background-color: #333; color: white; border-radius: 15px; font-weight: bold; font-size: 18px; }")
        db_layout.addWidget(QLabel(" 재고 조회 ", alignment=Qt.AlignmentFlag.AlignCenter, styleSheet="font-size: 26px; font-weight: 900;")); db_layout.addWidget(self.db_table, stretch=1); db_layout.addSpacing(15); db_layout.addWidget(self.btn_db_close)

        # 4. 재고 알림 팝업
        self.alarm_overlay = QFrame(); self.alarm_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 150);"); self.alarm_overlay.hide()
        self.alarm_popup_box = QFrame(self.alarm_overlay); self.alarm_popup_box.setFixedSize(1000, 750); self.alarm_popup_box.setStyleSheet("background-color: white; border-radius: 30px;")
        al_layout = QVBoxLayout(self.alarm_popup_box); al_layout.setContentsMargins(30, 30, 30, 30)
        self.alarm_table = QTableWidget(); self.alarm_table.setColumnCount(4)
        self.alarm_table.setHorizontalHeaderLabels(["카테고리", "제품명", "위치", "재고여부(O/X)"])
        self.alarm_table.setStyleSheet("QHeaderView::section { background-color: #FFDADA; color: #C0392B; font-weight: bold; }")
        self.alarm_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.btn_alarm_close = QPushButton("알림창 닫기"); self.btn_alarm_close.setFixedHeight(65); self.btn_alarm_close.setStyleSheet("QPushButton { background-color: #333; color: white; border-radius: 15px; font-weight: bold; font-size: 18px; }")
        al_layout.addWidget(QLabel("🚨 재고 알림", alignment=Qt.AlignmentFlag.AlignCenter, styleSheet="font-size: 26px; font-weight: 900; color: #E86464;")); al_layout.addWidget(self.alarm_table, stretch=1); al_layout.addSpacing(15); al_layout.addWidget(self.btn_alarm_close)

    def _connect_internal_events(self):
        self.btn_manual.clicked.connect(lambda: self.right_stack.setCurrentIndex(1))
        self.btn_back.clicked.connect(lambda: self.right_stack.setCurrentIndex(0))
        self.btn_db.clicked.connect(self.open_db_popup)
        self.btn_db_close.clicked.connect(self.db_overlay.hide)
        self.btn_alarm.clicked.connect(self.open_alarm_popup)
        self.btn_alarm_close.clicked.connect(self.alarm_overlay.hide)
        self.btn_reset.clicked.connect(self.open_popup); self.btn_no.clicked.connect(self.close_popup); self.btn_yes.clicked.connect(self.close_popup)
        self.map_btn.clicked.connect(self.open_map); self.btn_map_close.clicked.connect(self.close_map)
        self.patrol_row['btn'].clicked.connect(lambda: self.patrolTimeConfirmed.emit(self.patrol_row['slider'].value()))
        self.obstacle_row['btn'].clicked.connect(lambda: self.obstacleConfirmed.emit(self.obstacle_row['slider'].value()))
        self.btn_yes.clicked.connect(self.resetConfirmed.emit)
        self.btn_up.clicked.connect(lambda: self.moveCommand.emit("UP")); self.btn_down.clicked.connect(lambda: self.moveCommand.emit("DOWN"))
        self.btn_left.clicked.connect(lambda: self.moveCommand.emit("LEFT")); self.btn_right.clicked.connect(lambda: self.moveCommand.emit("RIGHT"))
        self.btn_stop.clicked.connect(lambda: self.moveCommand.emit("STOP")); self.btn_buzzer.clicked.connect(self.buzzerClicked.emit)
        self.btn_return.clicked.connect(self.returnClicked.emit); self.btn_emerg.clicked.connect(self.emergencyClicked.emit)

    # --- [데이터 연동 및 예외 처리] ---

    def set_last_patrol_time(self, time_str):
        """
        로직 담당자가 마지막 순찰 시간을 업데이트할 때 호출.
        데이터가 없으면 더미 데이터 표시.
        """
        if not time_str:
            time_str = "0000:00:00:00:00:00 (No Data)"
        self.logs_time.setText(time_str)

    def set_db_data(self, data_list):
        if not data_list:
            data_list = [
                ("-", "데이터가 없습니다", "-", "-", "-", "-"),
                ("DUMMY", "샘플 가공식품", "QR_SAMPLE", "0", "00:00:00", "Z-0")
            ]
        self.db_table.setRowCount(len(data_list))
        for r, row_data in enumerate(data_list):
            for c, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.db_table.setItem(r, c, item)

    def set_alarm_data(self, data_list):
        if not data_list:
            data_list = [
                ("없음", "부족 제품 없음", "All Clear", "O"),
                ("DUMMY", "샘플 생수 500ml", "Warehouse_01", "X")
            ]
        self.alarm_table.setRowCount(len(data_list))
        for r, row_data in enumerate(data_list):
            for c, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.alarm_table.setItem(r, c, item)

    def open_db_popup(self):
        if self.db_table.rowCount() == 0:
            self.set_db_data(None)
        self.db_overlay.show()
        self.center_popup(self.db_popup_box)
        self.dbRefreshRequested.emit()

    def open_alarm_popup(self):
        if self.alarm_table.rowCount() == 0:
            self.set_alarm_data(None)
        self.alarm_overlay.show()
        self.center_popup(self.alarm_popup_box)
        self.alarmRefreshRequested.emit()

    # --------------------------------

    def _init_timers(self):
        self.timer = QTimer(); self.timer.timeout.connect(self.update_frame)
        self.cap = cv2.VideoCapture(0); self.timer.start(30)

    def update_frame(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1); rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                qt_img = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.shape[1]*3, QImage.Format.Format_RGB888)
                self.cam_label.setPixmap(QPixmap.fromImage(qt_img).scaled(self.cam_label.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))

    def open_popup(self): self.overlay.show(); self.center_popup(self.popup_box)
    def close_popup(self): self.overlay.hide()
    def open_map(self): self.map_overlay.show(); self.center_popup(self.map_popup_box)
    def close_map(self): self.map_overlay.hide()
    def center_popup(self, box):
        qr = box.frameGeometry(); cp = self.rect().center(); qr.moveCenter(cp); box.move(qr.topLeft())
    def resizeEvent(self, event):
        for popup in [self.popup_box, self.map_popup_box, self.db_popup_box, self.alarm_popup_box]:
            if popup.parentWidget().isVisible(): self.center_popup(popup)
        super().resizeEvent(event)
