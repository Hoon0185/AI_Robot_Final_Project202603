import cv2
import os
import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QSlider, QFrame, QStackedWidget,
                             QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QTextCursor

# --- [추가: MinimapWidget 임포트] ---
try:
    from minimap import MinimapWidget
except ImportError:
    MinimapWidget = QFrame  # 파일이 없을 경우를 대비한 방어 코드

os.environ["OPENCV_LOG_LEVEL"] = "SILENT"

class RobotControlPanel(QWidget):
    patrolTimeConfirmed = pyqtSignal(int)
    obstacleConfirmed = pyqtSignal(int)
    moveCommand = pyqtSignal(str)
    patrolCommand = pyqtSignal()
    patrolConfirmed = pyqtSignal()
    buzzerClicked = pyqtSignal()
    returnClicked = pyqtSignal()
    emergencyClicked = pyqtSignal()
    resetConfirmed = pyqtSignal()
    dbRefreshRequested = pyqtSignal()
    alarmRefreshRequested = pyqtSignal()
    camModeToggleRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._init_styles()
        self.initUI()
        self._init_timers()
        self._connect_internal_events()

    def _init_styles(self):
        self.main_qss = "background-color: #F0F4F8; font-family: 'Malgun Gothic';"
        self.slider_qss = """
            QSlider::groove:horizontal { background: #E0E0E0; height: 8px; border-radius: 4px; }
            QSlider::sub-page:horizontal { background: #28A745; height: 8px; border-radius: 4px; }
            QSlider::handle:horizontal { background: #E86464; width: 18px; height: 18px; margin: -5px 0; border-radius: 9px; }
        """
        self.btn_confirm_qss = "QPushButton { background-color: #28A745; color: white; border-radius: 12px; font-size: 18px; font-weight: bold; } QPushButton:hover { background-color: #218838; }"
        self.btn_cancel_qss = "QPushButton { background-color: #E86464; color: white; border-radius: 12px; font-size: 18px; font-weight: bold; } QPushButton:hover { background-color: #C0392B; }"

    def initUI(self):
        self.setWindowTitle("Robot Management System")
        fixed_width = 1300
        fixed_height = 850
        self.setFixedSize(fixed_width, fixed_height)

        self.setWindowFlags(self.windowFlags() |
                            Qt.WindowType.CustomizeWindowHint |
                            Qt.WindowType.WindowMinimizeButtonHint |
                            Qt.WindowType.WindowCloseButtonHint)
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
        self.container_layout.addWidget(self.patrol_overlay, 0, 0)
        self.container_layout.addWidget(self.map_overlay, 0, 0)
        self.container_layout.addWidget(self.db_overlay, 0, 0)
        self.container_layout.addWidget(self.alarm_overlay, 0, 0)

    def _setup_left_panel(self):
        left_container = QVBoxLayout()
        
        # 카메라 영역 컨테이너 (레이블 + 전환 버튼)
        cam_frame = QFrame()
        cam_frame.setFixedSize(640, 480) # 버튼 영역 고려하여 약간 높임
        cam_frame.setStyleSheet("background-color: #2C2C2C; border-radius: 15px;")
        cam_box_layout = QVBoxLayout(cam_frame)
        cam_box_layout.setContentsMargins(10, 10, 10, 10)

        # 상단 제어 바 (모드 전환 버튼)
        cam_ctrl_layout = QHBoxLayout()
        self.lbl_cam_mode = QLabel("현재 모드: ROS 2 (저지연)")
        self.lbl_cam_mode.setStyleSheet("color: #AAAAAA; font-size: 12px; font-weight: normal;")
        
        self.btn_toggle_cam = QPushButton("🔄 연결 모드 전환")
        self.btn_toggle_cam.setFixedSize(130, 28)
        self.btn_toggle_cam.setStyleSheet("QPushButton { background-color: #444444; color: white; border-radius: 5px; font-size: 11px; } QPushButton:hover { background-color: #555555; }")
        self.btn_toggle_cam.clicked.connect(lambda: self.camModeToggleRequested.emit())
        
        cam_ctrl_layout.addWidget(self.lbl_cam_mode)
        cam_ctrl_layout.addStretch()
        cam_ctrl_layout.addWidget(self.btn_toggle_cam)
        cam_box_layout.addLayout(cam_ctrl_layout)

        self.cam_label = QLabel("캠 영상 송출")
        self.cam_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold; border: none;")
        cam_box_layout.addWidget(self.cam_label)
        
        left_container.addWidget(cam_frame, stretch=3)

        logs_frame = QFrame()
        logs_frame.setFixedHeight(60)
        logs_frame.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #D1D9E6;")
        logs_layout = QHBoxLayout(logs_frame)
        logs_layout.addWidget(QLabel("  🗓  마지막 순찰 시간  "))
        self.logs_time = QLabel()
        self.set_last_patrol_time(None)
        self.logs_time.setStyleSheet("background-color: #F0F4F8; padding: 8px; border-radius: 5px;")
        logs_layout.addStretch()
        logs_layout.addWidget(self.logs_time)
        left_container.addWidget(logs_frame)

        settings_frame = QFrame()
        settings_frame.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #D1D9E6;")
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.addWidget(QLabel("PATROL & OBSTACLE SETTINGS"))
        self.patrol_row = self._create_slider_row("순찰 시간 조절", 60, "(분)", min_val=10, max_val=120)
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
        # 전체 우측 레이아웃
        self.right_panel_layout = QVBoxLayout()
        self.right_panel_layout.setContentsMargins(0, 0, 0, 0)

        # 상단 스택 (메인 버튼 페이지 vs 수동 조작 페이지)
        self.right_stack = QStackedWidget()

        # [Page 1: Main Buttons]
        self.page_main = QWidget()
        layout_main = QVBoxLayout(self.page_main); layout_main.setContentsMargins(0, 0, 0, 0)

        self.btn_alarm = QPushButton("🔔 재고 알림")
        self.btn_alarm.setStyleSheet("QPushButton { border: 2px solid #E86464; background-color: #E86464; color: white; border-radius: 12px; font-size: 16px; font-weight: bold; } QPushButton:hover { background-color: #FF7676; border-color: #FF7676; } QPushButton:pressed { background-color: #D55555; padding-top: 5px; padding-left: 5px; }")

        self.btn_db = QPushButton("🗄 DB 조회")
        self.btn_db.setStyleSheet("QPushButton { border: 2px solid #AED9FF; background-color: #AED9FF; color: #333; border-radius: 12px; font-size: 16px; font-weight: bold; } QPushButton:hover { background-color: #C5E5FF; border-color: #C5E5FF; } QPushButton:pressed { background-color: #95C4EE; padding-top: 5px; padding-left: 5px; }")

        self.btn_manual = QPushButton("🕹 수동 조작")
        self.btn_manual.setStyleSheet("QPushButton { border: 2px solid #28A745; background-color: #FFFFFF; color: #28A745; border-radius: 12px; font-size: 16px; font-weight: bold; } QPushButton:hover { background-color: #EAF7ED; } QPushButton:pressed { background-color: #D4EDDA; padding-top: 5px; padding-left: 5px; }")

        self.btn_reset = QPushButton("🔄 초기 위치 명령")
        self.btn_reset.setStyleSheet("QPushButton { border: 2px solid #789D9E; background-color: #789D9E; color: white; border-radius: 12px; font-size: 16px; font-weight: bold; } QPushButton:hover { background-color: #8AADB0; border-color: #8AADB0; } QPushButton:pressed { background-color: #668B8C; padding-top: 5px; padding-left: 5px; }")

        self.btn_patrol = QPushButton("🚔 수동 순찰 명령")
        self.btn_patrol.setStyleSheet("QPushButton { border: 2px solid #0056b3; background-color: #0056b3; color: white; border-radius: 12px; font-size: 16px; font-weight: bold; } QPushButton:hover { background-color: #0069d9; border-color: #0062cc; } QPushButton:pressed { background-color: #004494; padding-top: 5px; padding-left: 5px; }")

        self.map_btn = QPushButton("🗺 미니맵\nView Full Map")
        self.map_btn.setStyleSheet("QPushButton { background-color: white; border: 2px solid #0056b3; color: #0056b3; font-size: 16px; font-weight: bold; border-radius: 12px; } QPushButton:hover { background-color: #E8F0FE; border-color: #004494; } QPushButton:pressed { background-color: #D2E3FC; padding-top: 5px; padding-left: 5px; }")

        for btn in [self.btn_alarm, self.btn_db, self.btn_manual, self.btn_reset, self.btn_patrol, self.map_btn]:
            btn.setFixedHeight(75) # 조작 패널 확보를 위해 높이 살짝 조절
            layout_main.addWidget(btn)
            layout_main.addSpacing(10)

        # [Page 2: Remote Control]
        self._setup_remote_page()

        self.right_stack.addWidget(self.page_main)
        self.right_stack.addWidget(self.page_remote)

        # 하단 공통 로그 콘솔
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet("""
            QTextEdit {
                background-color: #2C2C2C;
                color: #82E0AA;
                font-family: 'Consolas', 'Malgun Gothic';
                font-size: 12px;
                border-radius: 15px;
                border: 2px solid #D1D9E6;
                padding: 10px;
            }
        """)

        self.right_panel_layout.addWidget(self.right_stack, stretch=3)
        self.right_panel_layout.addSpacing(15)
        self.right_panel_layout.addWidget(self.log_console, stretch=2)

        self.main_layout.addLayout(self.right_panel_layout, 1)
        self.append_log("System Ready. Waiting for commands...")

    def _setup_remote_page(self):
        self.page_remote = QWidget()
        layout = QVBoxLayout(self.page_remote); layout.setContentsMargins(0, 0, 0, 0)
        remote_frame = QFrame()
        remote_frame.setStyleSheet("QFrame { background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #E3E9F0, stop:1 #FFFFFF); border-radius: 20px; border: 1px solid #CFD8E3; }")
        inner = QVBoxLayout(remote_frame); inner.setContentsMargins(15, 20, 15, 20)
        title = QLabel("🕹 수동 조작 모드"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); title.setStyleSheet("font-size: 20px; font-weight: 900; color: #2C3E50; border: none; background: transparent;")
        inner.addWidget(title); inner.addStretch(1)
        nav_card = QFrame(); nav_card.setStyleSheet("background: rgba(255, 255, 255, 0.5); border-radius: 20px; border: 1px solid #DDE4ED;")
        nav_grid = QGridLayout(nav_card)
        nav_style = "QPushButton { background-color: white; border: 2px solid #28A745; border-radius: 20px; font-size: 28px; min-height: 70px; min-width: 60px; color: #28A745; } QPushButton:hover { background-color: #EAF7ED; border-color: #218838; } QPushButton:pressed { background-color: #D4EDDA; padding-top: 5px; padding-left: 5px; }"
        stop_style = "QPushButton { background-color: white; border: 2px solid #5A6268; border-radius: 20px; font-size: 18px; min-height: 70px; min-width: 60px; color: #5A6268; } QPushButton:hover { background-color: #F8F9FA; } QPushButton:pressed { background-color: #E2E6EA; padding-top: 5px; padding-left: 5px; }"
        self.btn_up = QPushButton("▲"); self.btn_up.setStyleSheet(nav_style)
        self.btn_down = QPushButton("▼"); self.btn_down.setStyleSheet(nav_style)
        self.btn_left = QPushButton("◀"); self.btn_left.setStyleSheet(nav_style)
        self.btn_right = QPushButton("▶"); self.btn_right.setStyleSheet(nav_style)
        self.btn_stop = QPushButton("정지"); self.btn_stop.setStyleSheet(stop_style)
        nav_grid.addWidget(self.btn_up, 0, 1); nav_grid.addWidget(self.btn_left, 1, 0); nav_grid.addWidget(self.btn_stop, 1, 1); nav_grid.addWidget(self.btn_right, 1, 2); nav_grid.addWidget(self.btn_down, 2, 1)
        inner.addWidget(nav_card); inner.addStretch(1)
        extra_h_box = QHBoxLayout()
        ex_style = "QPushButton { background-color: white; border-radius: 12px; font-weight: bold; min-height: 65px; font-size: 14px; border: 2px solid %s; color: %s; } QPushButton:hover { background-color: %s; } QPushButton:pressed { padding-top: 5px; padding-left: 5px; background-color: %s; }"
        self.btn_buzzer = QPushButton("🔊\n부저"); self.btn_buzzer.setStyleSheet(ex_style % ("#789D9E", "#4A6E6F", "#F0F7F7", "#D9E8E8"))
        self.btn_return = QPushButton("🔄\n순찰복귀"); self.btn_return.setStyleSheet(ex_style % ("#789D9E", "#4A6E6F", "#F0F7F7", "#D9E8E8"))
        self.btn_emerg = QPushButton("🚨\n비상정지"); self.btn_emerg.setStyleSheet("QPushButton { background-color: #E86464; border-radius: 12px; font-weight: bold; min-height: 65px; font-size: 14px; border: 2px solid #E86464; color: white; } QPushButton:hover { background-color: #FF7676; border-color: #FF7676; } QPushButton:pressed { background-color: #C0392B; padding-top: 5px; padding-left: 5px; }")
        extra_h_box.addWidget(self.btn_buzzer); extra_h_box.addWidget(self.btn_return); extra_h_box.addWidget(self.btn_emerg)
        inner.addLayout(extra_h_box); inner.addStretch(1)
        self.btn_back = QPushButton("◀ 메인 화면으로 돌아가기"); self.btn_back.setFixedHeight(50); self.btn_back.setStyleSheet("QPushButton { background-color: #333; color: white; border-radius: 12px; font-weight: bold; } QPushButton:hover { background-color: #555; } QPushButton:pressed { padding-top: 3px; padding-left: 3px; }")
        inner.addWidget(self.btn_back); layout.addWidget(remote_frame)

    def _setup_popups(self):
        popup_frame_style = "background-color: white; border-radius: 20px; border: 1px solid #DDE4ED;"
        popup_title_style = "font-size: 22px; font-weight: bold; color: #333; border: none; background: transparent;"

        # --- 초기 위치 명령 팝업 ---
        self.overlay = QFrame(); self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 100);"); self.overlay.hide()
        self.popup_box = QFrame(self.overlay); self.popup_box.setFixedSize(450, 280); self.popup_box.setStyleSheet(popup_frame_style)
        p_layout = QVBoxLayout(self.popup_box); p_layout.setContentsMargins(30, 40, 30, 40)
        p_title = QLabel("로봇의 처음 위치로\n돌아가시겠습니까?"); p_title.setAlignment(Qt.AlignmentFlag.AlignCenter); p_title.setStyleSheet(popup_title_style)
        btn_row = QHBoxLayout(); btn_row.setSpacing(15)
        self.btn_yes = QPushButton("예"); self.btn_yes.setFixedHeight(55); self.btn_yes.setStyleSheet(self.btn_confirm_qss)
        self.btn_no = QPushButton("아니오"); self.btn_no.setFixedHeight(55); self.btn_no.setStyleSheet(self.btn_cancel_qss)
        btn_row.addWidget(self.btn_yes); btn_row.addWidget(self.btn_no); p_layout.addWidget(p_title); p_layout.addStretch(); p_layout.addLayout(btn_row)

        # --- 수동 순찰 명령 팝업 ---
        self.patrol_overlay = QFrame(); self.patrol_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 100);"); self.patrol_overlay.hide()
        self.patrol_popup_box = QFrame(self.patrol_overlay); self.patrol_popup_box.setFixedSize(450, 280); self.patrol_popup_box.setStyleSheet(popup_frame_style)
        pat_layout = QVBoxLayout(self.patrol_popup_box); pat_layout.setContentsMargins(30, 40, 30, 40)
        pat_title = QLabel("자율 주행 순찰을\n시작하시겠습니까?"); pat_title.setAlignment(Qt.AlignmentFlag.AlignCenter); pat_title.setStyleSheet(popup_title_style)
        pat_btn_row = QHBoxLayout(); pat_btn_row.setSpacing(15)
        self.btn_patrol_yes = QPushButton("시작"); self.btn_patrol_yes.setFixedHeight(55); self.btn_patrol_yes.setStyleSheet(self.btn_confirm_qss)
        self.btn_patrol_no = QPushButton("취소"); self.btn_patrol_no.setFixedHeight(55); self.btn_patrol_no.setStyleSheet(self.btn_cancel_qss)
        pat_btn_row.addWidget(self.btn_patrol_yes); pat_btn_row.addWidget(self.btn_patrol_no); pat_layout.addWidget(pat_title); pat_layout.addStretch(); pat_layout.addLayout(pat_btn_row)

        # --- 미니맵 오버레이 [수정됨] ---
        self.map_overlay = QFrame(); self.map_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 150);"); self.map_overlay.hide()
        self.map_popup_box = QFrame(self.map_overlay); self.map_popup_box.setFixedSize(850, 700); self.map_popup_box.setStyleSheet("background-color: white; border-radius: 30px;")
        m_layout = QVBoxLayout(self.map_popup_box); m_layout.setContentsMargins(30, 30, 30, 30)

        # --- [수정: 단순 QFrame을 MinimapWidget으로 교체] ---
        self.minimap = MinimapWidget()
        self.minimap.setStyleSheet("background-color: #F8F9FA; border: 1px solid #DDE4ED; border-radius: 15px;")
        # -----------------------------------------------

        self.btn_map_close = QPushButton("닫기"); self.btn_map_close.setFixedHeight(65); self.btn_map_close.setStyleSheet("QPushButton { background-color: #28A745; color: white; border-radius: 18px; font-size: 22px; font-weight: bold; } QPushButton:hover { background-color: #218838; }")
        m_layout.addWidget(QLabel("로봇 실시간 위치", alignment=Qt.AlignmentFlag.AlignCenter, styleSheet="font-size: 26px; font-weight: 900; border:none;"))
        m_layout.addWidget(self.minimap, stretch=1) # self.minimap을 레이아웃에 추가
        m_layout.addSpacing(20); m_layout.addWidget(self.btn_map_close)

        self.db_overlay = QFrame(); self.db_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 150);"); self.db_overlay.hide()
        self.db_popup_box = QFrame(self.db_overlay); self.db_popup_box.setFixedSize(1000, 750); self.db_popup_box.setStyleSheet("background-color: white; border-radius: 30px;")
        db_layout = QVBoxLayout(self.db_popup_box); db_layout.setContentsMargins(30, 30, 30, 30)
        self.db_table = QTableWidget(); self.db_table.setColumnCount(6)
        self.db_table.setHorizontalHeaderLabels(["카테고리", "제품이름", "제품번호(QR)", "기준 수량", "동기화 시각", "위치"])
        self.db_table.setStyleSheet("QHeaderView::section { background-color: #AED9FF; font-weight: bold; } QTableWidget { border-radius: 10px; border: 1px solid #DDE4ED; }")
        self.db_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.btn_db_close = QPushButton("조회창 닫기"); self.btn_db_close.setFixedHeight(65); self.btn_db_close.setStyleSheet("QPushButton { background-color: #333; color: white; border-radius: 15px; font-weight: bold; font-size: 18px; } QPushButton:hover { background-color: #555; }")
        db_layout.addWidget(QLabel(" 재고 조회 ", alignment=Qt.AlignmentFlag.AlignCenter, styleSheet="font-size: 26px; font-weight: 900; border:none;")); db_layout.addWidget(self.db_table, stretch=1); db_layout.addSpacing(15); db_layout.addWidget(self.btn_db_close)

        self.alarm_overlay = QFrame(); self.alarm_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 150);"); self.alarm_overlay.hide()
        self.alarm_popup_box = QFrame(self.alarm_overlay); self.alarm_popup_box.setFixedSize(1000, 750); self.alarm_popup_box.setStyleSheet("background-color: white; border-radius: 30px;")
        al_layout = QVBoxLayout(self.alarm_popup_box); al_layout.setContentsMargins(30, 30, 30, 30)
        self.alarm_table = QTableWidget(); self.alarm_table.setColumnCount(4)
        self.alarm_table.setHorizontalHeaderLabels(["카테고리", "제품명", "위치", "재고여부(O/X)"])
        self.alarm_table.setStyleSheet("QHeaderView::section { background-color: #FFDADA; color: #C0392B; font-weight: bold; } QTableWidget { border-radius: 10px; border: 1px solid #DDE4ED; }")
        self.alarm_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.btn_alarm_close = QPushButton("알림창 닫기"); self.btn_alarm_close.setFixedHeight(65); self.btn_alarm_close.setStyleSheet("QPushButton { background-color: #333; color: white; border-radius: 15px; font-weight: bold; font-size: 18px; } QPushButton:hover { background-color: #555; }")
        al_layout.addWidget(QLabel("🚨 재고 알림", alignment=Qt.AlignmentFlag.AlignCenter, styleSheet="font-size: 26px; font-weight: 900; color: #E86464; border:none;")); al_layout.addWidget(self.alarm_table, stretch=1); al_layout.addSpacing(15); al_layout.addWidget(self.btn_alarm_close)

    def _connect_internal_events(self):
        self.btn_manual.clicked.connect(lambda: self.right_stack.setCurrentIndex(1))
        self.btn_back.clicked.connect(lambda: self.right_stack.setCurrentIndex(0))
        self.btn_db.clicked.connect(self.open_db_popup)
        self.btn_db_close.clicked.connect(self.db_overlay.hide)
        self.btn_alarm.clicked.connect(self.open_alarm_popup)
        self.btn_alarm_close.clicked.connect(self.alarm_overlay.hide)

        self.btn_reset.clicked.connect(self.open_popup)
        self.btn_no.clicked.connect(self.close_popup)
        self.btn_yes.clicked.connect(self.close_popup)
        self.btn_yes.clicked.connect(self.resetConfirmed.emit)

        self.btn_patrol.clicked.connect(self.open_patrol_popup)
        self.btn_patrol_no.clicked.connect(self.close_patrol_popup)
        self.btn_patrol_yes.clicked.connect(self.close_patrol_popup)
        self.btn_patrol_yes.clicked.connect(self.patrolConfirmed.emit)

        self.map_btn.clicked.connect(self.open_map); self.btn_map_close.clicked.connect(self.close_map)
        self.patrol_row['btn'].clicked.connect(lambda: self.patrolTimeConfirmed.emit(self.patrol_row['slider'].value()))
        self.obstacle_row['btn'].clicked.connect(lambda: self.obstacleConfirmed.emit(self.obstacle_row['slider'].value()))

        self.btn_up.clicked.connect(lambda: self.moveCommand.emit("UP"))
        self.btn_down.clicked.connect(lambda: self.moveCommand.emit("DOWN"))
        self.btn_left.clicked.connect(lambda: self.moveCommand.emit("LEFT"))
        self.btn_right.clicked.connect(lambda: self.moveCommand.emit("RIGHT"))
        self.btn_stop.clicked.connect(lambda: self.moveCommand.emit("STOP"))
        self.btn_buzzer.clicked.connect(self.buzzerClicked.emit)
        self.btn_return.clicked.connect(self.returnClicked.emit)
        self.btn_emerg.clicked.connect(self.emergencyClicked.emit)

    def open_patrol_popup(self): self.patrol_overlay.show(); self.center_popup(self.patrol_popup_box)
    def close_patrol_popup(self): self.patrol_overlay.hide()

    def open_popup(self): self.overlay.show(); self.center_popup(self.popup_box)
    def close_popup(self): self.overlay.hide()

    def set_last_patrol_time(self, time_str):
        if not time_str: time_str = "0000:00:00:00:00:00 (No Data)"
        self.logs_time.setText(time_str)

    def set_db_data(self, data_list):
        if not data_list: data_list = [("-", "데이터가 없습니다", "-", "-", "-", "-")]
        self.db_table.setRowCount(len(data_list))
        for r, row_data in enumerate(data_list):
            for c, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.db_table.setItem(r, c, item)

    def set_alarm_data(self, data_list):
        if not data_list: data_list = [("없음", "부족 제품 없음", "All Clear", "O")]
        self.alarm_table.setRowCount(len(data_list))
        for r, row_data in enumerate(data_list):
            for c, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.alarm_table.setItem(r, c, item)

    def open_db_popup(self):
        if self.db_table.rowCount() == 0: self.set_db_data(None)
        self.db_overlay.show(); self.center_popup(self.db_popup_box)
        self.dbRefreshRequested.emit()

    def open_alarm_popup(self):
        if self.alarm_table.rowCount() == 0: self.set_alarm_data(None)
        self.alarm_overlay.show(); self.center_popup(self.alarm_popup_box)
        self.alarmRefreshRequested.emit()

    def _init_timers(self):
        # [모드 공통] RTSP 직접 연결용 타이머 및 객체 초기화
        self.direct_rtsp_timer = QTimer()
        self.direct_rtsp_timer.timeout.connect(self.update_frame_direct)
        self.direct_cap = None
        self.direct_rtsp_url = ""

    def start_direct_rtsp(self, url):
        """ROS 구독 실패 시 호출되는 비상 직접 연결 모드"""
        print(f"📡 [UI] RTSP 직접 연결 시도... ({url})")
        self.direct_rtsp_url = url
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
        self.direct_cap = cv2.VideoCapture(url)
        self.direct_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.direct_rtsp_timer.start(30) # 30ms 간격으로 업데이트

    def stop_direct_rtsp(self):
        if self.direct_rtsp_timer.isActive():
            self.direct_rtsp_timer.stop()
        if self.direct_cap:
            self.direct_cap.release()
            self.direct_cap = None

    def update_frame_direct(self):
        """UI에서 직접 카메라에 접속하여 영상을 갱신합니다."""
        if self.direct_cap and self.direct_cap.isOpened():
            # [최적화] 누적 지연 방지 (버퍼 비우기)
            last_frame = None
            while True:
                grabbed = self.direct_cap.grab()
                if not grabbed: break
                ret, frame = self.direct_cap.retrieve()
                if ret: last_frame = frame
            
            if last_frame is not None:
                frame = cv2.flip(last_frame, -1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                bytes_per_line = ch * w

                qt_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qt_img).scaled(
                    self.cam_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.cam_label.setPixmap(pixmap)
        else:
            # 연결 실패 시 재시도 로직 (옵션)
            pass

    def display_compressed_image(self, data):
        """백엔드 노드에서 전송받은 압축 이미지를 실시간으로 화면에 표시합니다."""
        try:
            import numpy as np
            # 바이너리 데이터를 이미지로 변환
            np_arr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is not None:
                # 상하 반전 (필요한 경우) 및 RGB 변환
                frame = cv2.flip(frame, -1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                bytes_per_line = ch * w

                qt_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                
                # 라벨 크기에 맞춰 최신 프레임 표시
                pixmap = QPixmap.fromImage(qt_img).scaled(
                    self.cam_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.cam_label.setPixmap(pixmap)
        except Exception as e:
            print(f"이미지 디코딩 에러: {e}")
    def open_map(self):
        self.map_overlay.show()
        self.center_popup(self.map_popup_box)
        # --- [추가: 맵이 열릴 때 강제로 다시 그리게 함] ---
        if hasattr(self, 'minimap'):
            self.minimap.update_map_display()

    def close_map(self): self.map_overlay.hide()

    def center_popup(self, box):
        qr = box.frameGeometry(); cp = self.rect().center(); qr.moveCenter(cp); box.move(qr.topLeft())

    def resizeEvent(self, event):
        for popup in [self.popup_box, self.patrol_popup_box, self.map_popup_box, self.db_popup_box, self.alarm_popup_box]:
            if popup.parentWidget().isVisible(): self.center_popup(popup)
        super().resizeEvent(event)

    def append_log(self, message):
            """우하단 로그 콘솔에 텍스트를 추가하고 자동으로 스크롤합니다."""
            # 현재 시간을 [HH:MM:SS] 형식으로 생성
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"
            # 로그 메시지 추가
            self.log_console.append(log_entry)
            # 로그가 쌓일 때 자동으로 가장 아래로 스크롤
            self.log_console.moveCursor(QTextCursor.MoveOperation.End)
