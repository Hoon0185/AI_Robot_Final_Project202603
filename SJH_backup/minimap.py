import os
import yaml
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

class MinimapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 1. 위젯 자체가 부모를 뚫고 커지지 않도록 크기 정책 설정
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(100, 100) # 최소 크기만 고정

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # 맵을 표시할 라벨
        self.map_label = QLabel("맵 로딩 중...")
        self.map_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.map_label.setStyleSheet("background-color: #222; color: white; border: 1px solid #444;")

        # 2. 라벨이 이미지 크기에 따라 늘어나는 것을 방지
        self.map_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.map_label.setScaledContents(False) # 직접 계산해서 그릴 것이므로 False

        self.layout.addWidget(self.map_label)

        self.map_data = None
        self.map_info = {'resolution': 0.05, 'origin': [0.0, 0.0, 0.0]}
        self.yaml_path = os.path.join(os.path.dirname(__file__), 'my_store_map_01.yaml')

        self.load_map_data()

    def load_map_data(self):
        if not os.path.exists(self.yaml_path):
            self.map_label.setText("YAML NotFound")
            return

        try:
            with open(self.yaml_path, 'r') as f:
                config = yaml.safe_load(f)

            self.map_info['resolution'] = config.get('resolution', 0.05)
            self.map_info['origin'] = config.get('origin', [0.0, 0.0, 0.0])
            pgm_filename = config.get('image', 'my_store_map_01.pgm')
            pgm_path = os.path.join(os.path.dirname(self.yaml_path), pgm_filename)

            if os.path.exists(pgm_path):
                # 원본 이미지를 로드하되, 화면에 바로 뿌리지 않고 보관만 함
                self.map_data = QPixmap.fromImage(QImage(pgm_path))
                print(f"[SYSTEM] 미니맵 로드 성공: {self.map_data.width()}x{self.map_data.height()}")
                # 로드 후 UI 갱신 유도
                self.update_map_display()
            else:
                self.map_label.setText("PGM NotFound")

        except Exception as e:
            self.map_label.setText(f"Error: {e}")

    def update_map_display(self):
        """현재 라벨의 '실제 크기'에 맞춰 이미지를 스케일링하여 표시"""
        if self.map_data and not self.map_data.isNull():
            # 라벨의 현재 크기 가져오기
            target_size = self.map_label.size()

            # 3. 라벨 크기가 0보다 클 때만 스케일링 수행 (초기 로딩 시 방지)
            if target_size.width() > 0 and target_size.height() > 0:
                scaled_pixmap = self.map_data.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.map_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        """위젯 크기가 변할 때(부모 창이 커질 때 등)만 이미지를 다시 계산"""
        super().resizeEvent(event)
        # 4. 리사이즈 시 즉시 업데이트하여 꽉 차게 유지
        self.update_map_display()

    # world_to_pixel 함수는 동일 (생략)
