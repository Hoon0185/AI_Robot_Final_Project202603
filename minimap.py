import os
import yaml
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PyQt6.QtCore import Qt, QPoint, QRectF

class MinimapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(100, 100)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.map_label = QLabel("맵 로딩 중...")
        self.map_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.map_label.setStyleSheet("background-color: #222; color: white; border: 1px solid #444;")
        self.map_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.layout.addWidget(self.map_label)

        self.map_original = None
        self.map_info = {'resolution': 0.05, 'origin': [-3.26, -0.859, 0.0]}
        self.yaml_path = os.path.join(os.path.dirname(__file__), 'my_store_map_01.yaml')
        self.robot_pose = (0.0, 0.0)

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
                self.map_original = QPixmap.fromImage(QImage(pgm_path))
                # 초기 로드 시에는 사이즈가 0일 수 있으므로 여기서 update_map_display를 호출하지 않고
                # showEvent나 resizeEvent에 맡깁니다.
            else:
                self.map_label.setText("PGM NotFound")
        except Exception as e:
            self.map_label.setText(f"Error: {e}")

    def get_ui_coords(self, world_x, world_y, pixmap_rect):
        """실제 좌표를 현재 화면(UI)상의 픽셀 좌표로 변환"""
        if self.map_original is None: return QPoint(0, 0)

        res = self.map_info['resolution']
        origin_x = self.map_info['origin'][0]
        origin_y = self.map_info['origin'][1]

        # 1. 원본 이미지 기준 픽셀 좌표
        orig_px = (world_x - origin_x) / res
        orig_py = self.map_original.height() - ((world_y - origin_y) / res)

        # 2. UI에 출력된 pixmap의 스케일 비율 계산
        scale_x = pixmap_rect.width() / self.map_original.width()
        scale_y = pixmap_rect.height() / self.map_original.height()

        # 3. 라벨 내 실제 이미지가 시작되는 오프셋 더하기
        final_x = pixmap_rect.left() + (orig_px * scale_x)
        final_y = pixmap_rect.top() + (orig_py * scale_y)

        return QPoint(int(final_x), int(final_y))

    def update_map_display(self):
        if self.map_original is None or self.map_original.isNull():
            return

        # 1. 먼저 맵 이미지만 라벨 크기에 맞춰 준비
        target_size = self.map_label.size()
        # 중요: 사이즈가 아직 결정되지 않았다면 그리기를 중단합니다.
        if target_size.width() <= 0 or target_size.height() <= 0: return

        scaled_map = self.map_original.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # 2. 맵이 라벨 중앙에 배치될 때의 실제 위치(Rect) 계산
        # (중앙 정렬이므로 여백이 생길 수 있음)
        label_w, label_h = target_size.width(), target_size.height()
        map_w, map_h = scaled_map.width(), scaled_map.height()
        map_rect = QRectF((label_w - map_w) / 2, (label_h - map_h) / 2, map_w, map_h)

        # 3. 최종 Pixmap 생성 및 그리기 시작
        final_canvas = QPixmap(target_size)
        final_canvas.fill(QColor("#222222")) # 배경색

        painter = QPainter(final_canvas)
        painter.drawPixmap(map_rect.toRect(), scaled_map) # 맵 먼저 그리기

        # 선명한 마커를 위해 안티앨리어싱 활성화
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 4. 좌표 변환 후 원점(0,0)과 로봇 그리기
        origin_pt = self.get_ui_coords(0.0, 0.0, map_rect)
        robot_pt = self.get_ui_coords(self.robot_pose[0], self.robot_pose[1], map_rect)

        # 원점 십자선 (녹색, 1px)
        painter.setPen(QPen(QColor(0, 255, 0), 1))
        painter.drawLine(origin_pt.x() - 6, origin_pt.y(), origin_pt.x() + 6, origin_pt.y())
        painter.drawLine(origin_pt.x(), origin_pt.y() - 6, origin_pt.x(), origin_pt.y() + 6)

        # 로봇 점 (빨간색, 테두리 없이 반지름 2.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 0, 0))
        painter.drawEllipse(robot_pt, 3, 3) # 화면상에서 지름 6픽셀 정도로 선명하게 보임

        painter.end()
        self.map_label.setPixmap(final_canvas)

    def set_robot_pose(self, x, y):
        self.robot_pose = (x, y)
        self.update_map_display()

    def showEvent(self, event):
        """위젯이 화면에 표시될 때 호출되어 올바른 사이즈로 맵을 그립니다."""
        super().showEvent(event)
        self.update_map_display()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_map_display()
