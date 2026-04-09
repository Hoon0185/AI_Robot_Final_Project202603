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
    # 해당 모델 경로는 직접 다운로드 받은 후
    # PC에서 모델 비교를 하기위해 PC의 절대 경로로 설정합니다.
    def __init__(self, model_path="/home/bird99/Desktop/database/heavy/products.pt"):
        self.model = YOLO(model_path)

    def predict(self, frame):
        results = self.model(frame, conf=0.6, iou=0.3, verbose=False)
        items = []

        if results and len(results[0].boxes) > 0:
            for box in results[0].boxes:
                cls_id = int(box.cls[0])
                if cls_id == 88:
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
                print(f"DEBUG [Product]: {item.class_name}(ID:{item.class_id}) 확인됨")
                items.append(item)

        return items
