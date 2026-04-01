import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QImage, QPixmap, QColor
from PyQt6.QtCore import Qt
import numpy as np

class MinimapHandler(Node):
    def __init__(self, ui_label: QLabel, debug_mode=True):
        """
        :param ui_label: robot_ui.py의 self.label_map_display 객체
        :param debug_mode: True일 경우 테스트용 가상 맵 출력
        """
        super().__init__('minimap_handler')
        self.display_label = ui_label
        self.debug_mode = debug_mode

        if not self.debug_mode:
            # ROS 2 정식 맵 토픽 설정 (QoS 필수)
            from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

            map_qos = QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
                durability=DurabilityPolicy.TRANSIENT_LOCAL # 맵 데이터 수신 핵심 설정
            )

            self.subscription = self.create_subscription(
                OccupancyGrid,
                '/map',
                self.map_callback,
                map_qos
            )
            self.get_logger().info("Minimap: Waiting for real /map topic...")
        else:
            self.get_logger().info("Minimap: DEBUG MODE - Showing Virtual Map")
            self._generate_debug_map()

    def map_callback(self, msg):
        """실제 터틀봇의 OccupancyGrid 데이터를 QImage로 변환"""
        width = msg.info.width
        height = msg.info.height

        # 1D 데이터를 2D 넘파이 배열로 변환
        map_data = np.array(msg.data, dtype=np.int8).reshape((height, width))

        # QImage 생성 (RGB32 형식)
        img = QImage(width, height, QImage.Format.Format_RGB32)

        for y in range(height):
            for x in range(width):
                val = map_data[y, x]
                # ROS 맵 값 매핑: -1(알수없음), 0(통로), 100(벽)
                if val == 100:
                    color = QColor(44, 62, 80).rgb()   # 벽: 진한 남색
                elif val == 0:
                    color = QColor(255, 255, 255).rgb() # 통로: 흰색
                else:
                    color = QColor(220, 220, 220).rgb() # 미탐사: 연회색

                # 이미지 원점 보정 (ROS는 좌하단, Qt는 좌상단이 원점)
                img.setPixel(x, height - 1 - y, color)

        self._update_display(img)

    def _generate_debug_map(self):
        """로봇 연결이 없을 때 UI 확인용 가상 맵 생성"""
        w, h = 400, 400
        img = QImage(w, h, QImage.Format.Format_RGB32)
        img.fill(QColor(255, 255, 255)) # 배경 흰색

        # 가상 벽 그리기 (외곽선 및 내부 장애물)
        for x in range(w):
            for y in range(h):
                # 테두리 벽
                if x < 10 or x > 390 or y < 10 or y > 390:
                    img.setPixel(x, y, QColor(44, 62, 80).rgb())
                # 중앙 구조물 시뮬레이션
                if (150 < x < 250 and 180 < y < 220) or (180 < x < 220 and 100 < y < 300):
                    img.setPixel(x, y, QColor(44, 62, 80).rgb())

        self._update_display(img)

    def _update_display(self, q_img):
        """변환된 이미지를 UI 레이블 크기에 맞춰 출력"""
        if not self.display_label:
            return

        pixmap = QPixmap.fromImage(q_img)
        # 레이블 크기에 맞게 부드럽게 스케일링
        scaled_pixmap = pixmap.scaled(
            self.display_label.width(),
            self.display_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.display_label.setPixmap(scaled_pixmap)

    def clear_map(self):
        """맵 데이터 초기화"""
        self.display_label.clear()
        self.display_label.setText("No Map Data Available")
