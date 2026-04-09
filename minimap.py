import os
import yaml
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QBrush
from PyQt6.QtCore import Qt, QPoint, QRectF

class MinimapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 200) # 최소 사이즈를 조금 키움

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.map_label = QLabel("맵 로딩 중...")
        self.map_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.map_label.setStyleSheet("background-color: #222; color: white; border: 1px solid #444; border-radius: 15px;")
        self.map_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.layout.addWidget(self.map_label)

        self.map_original = None
        # 기본값 설정 (실제 YAML 로드 시 덮어씌워짐)
        self.map_info = {'resolution': 0.05, 'origin': [0.0, 0.0, 0.0]}
        self.yaml_path = os.path.join(os.path.dirname(__file__), 'my_store_map_02.yaml')
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

            pgm_filename = config.get('image', 'my_store_map_02.pgm')
            pgm_path = os.path.join(os.path.dirname(self.yaml_path), pgm_filename)

            if os.path.exists(pgm_path):
                img = QImage(pgm_path)
                if img.isNull():
                    self.map_label.setText("PGM Load Failed")
                else:
                    self.map_original = QPixmap.fromImage(img)
            else:
                self.map_label.setText("PGM NotFound")
        except Exception as e:
            self.map_label.setText(f"Error: {e}")

    def get_ui_coords(self, world_x, world_y, pixmap_rect):
        """실제 월드 좌표(m)를 UI상의 픽셀 좌표로 정밀 변환"""
        if self.map_original is None: return QPoint(0, 0)

        res = self.map_info['resolution']
        origin_x = self.map_info['origin'][0]
        origin_y = self.map_info['origin'][1]

        # 1. 원본 이미지 기준 픽셀 좌표 계산
        # (현재좌표 - 시작점좌표) / 해상도 = 픽셀 위치
        orig_px = (world_x - origin_x) / res

        # PGM 이미지는 Y축이 위에서 아래로 증가하므로 전체 높이에서 빼줌
        orig_py = self.map_original.height() - ((world_y - origin_y) / res)

        # 2. UI 화면 비율(Scale) 계산
        scale_x = pixmap_rect.width() / self.map_original.width()
        scale_y = pixmap_rect.height() / self.map_original.height()

        # 3. 라벨 내 실제 이미지가 시작되는 위치(Offset)를 더함
        final_x = pixmap_rect.left() + (orig_px * scale_x)
        final_y = pixmap_rect.top() + (orig_py * scale_y)

        return QPoint(int(final_x), int(final_y))

    def update_map_display(self):
        if self.map_original is None or self.map_original.isNull():
            return

        target_size = self.map_label.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return

        # 1. 맵 이미지 스케일링 (비율 유지)
        scaled_map = self.map_original.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # 2. 맵이 그려질 중앙 영역(Rect) 계산
        label_w, label_h = target_size.width(), target_size.height()
        map_w, map_h = scaled_map.width(), scaled_map.height()
        map_rect = QRectF((label_w - map_w) / 2, (label_h - map_h) / 2, map_w, map_h)

        # 3. 캔버스 준비
        final_canvas = QPixmap(target_size)
        final_canvas.fill(QColor("#222222")) # 어두운 배경색

        painter = QPainter(final_canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) # 부드러운 그리기 활성화

        # 맵 그리기
        painter.drawPixmap(map_rect.toRect(), scaled_map)

        # 4. 좌표 변환 및 마커 그리기
        origin_pt = self.get_ui_coords(0.0, 0.0, map_rect)
        robot_pt = self.get_ui_coords(self.robot_pose[0], self.robot_pose[1], map_rect)

        # [원점 표시] 초록색 십자선
        painter.setPen(QPen(QColor(0, 255, 0), 2))
        painter.drawLine(origin_pt.x() - 8, origin_pt.y(), origin_pt.x() + 8, origin_pt.y())
        painter.drawLine(origin_pt.x(), origin_pt.y() - 8, origin_pt.x(), origin_pt.y() + 8)

        # [로봇 표시] 빨간색 원 + 흰색 테두리 (크기를 키워서 시인성 확보)
        # 테두리(외곽선) 그리기
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setBrush(QBrush(QColor(255, 0, 0))) # 내부 빨간색
        painter.drawEllipse(robot_pt, 6, 6) # 반지름 6 (총 지름 12px)

        painter.end()
        self.map_label.setPixmap(final_canvas)

    def set_robot_pose(self, x, y):
        """외부(patrol_interface 등)에서 로봇 좌표를 업데이트할 때 호출"""
        self.robot_pose = (x, y)
        self.update_map_display()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_map_display()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_map_display()
