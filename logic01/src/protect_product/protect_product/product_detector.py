from ultralytics import YOLO

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class DetectionResult:
    box: List[int] = field(default_factory=lambda: [0, 0, 0, 0])
    class_id: Optional[int] = None
    class_name: str = "Unknown"
    score: float = 0.0
    raw_data: str = ""       # QR 데이터(바코드 내용) 저장용
    is_verified: bool = False # DB 검증 완료 여부

class ProductDetector:
    def __init__(self, model_path=None):
        import os
        if model_path is None:
            # 현재 파일 위치 기준 상대 경로로 models 폴더 찾기
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 구조: src/protect_product/protect_product/product_detector.py
            # 모델 위치: src/protect_product/models/products.pt
            model_path = os.path.join(current_dir, "..", "models", "products.pt")
            
            if not os.path.exists(model_path):
                # 다른 후보 경로 확인 (심볼릭 링크 등 고려)
                alt_path = "/home/penguin/Documents/GitHub/AI_Robot_Final_Project202603/logic01/src/protect_product/models/products.pt"
                if os.path.exists(alt_path):
                    model_path = alt_path

        print(f"DEBUG [Product]: Loading model from {model_path}")
        try:
            self.model = YOLO(model_path)
        except Exception as e:
            print(f"ERROR [Product]: Failed to load YOLO model: {e}")
            self.model = None

    def predict(self, frame):
        if self.model is None:
            return []
        results = self.model(frame, conf=0.6, iou=0.3, verbose=False)
        items = []

        if results and len(results[0].boxes) > 0:
            for box in results[0].boxes:
                cls_id = int(box.cls[0])
                if cls_id == 89:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # 객체 생성 방식으로 변경
                item = DetectionResult(
                    box=[x1, y1, x2, y2],
                    class_id=cls_id,
                    class_name=self.model.names[cls_id],
                    score=float(box.conf[0])
                )

                # 리스트에 넣기 전 확인 로그
                print(f"DEBUG [Product]: {item.class_name}(ID:{item.class_id}) 추가됨")
                items.append(item)

        return items
