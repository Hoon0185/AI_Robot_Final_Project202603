from ultralytics import YOLO

class ProductDetector:
    def __init__(self, model_path="/home/bird99/Desktop/database/heavy/products.pt"):
        self.model = YOLO(model_path)

    def predict(self, frame):
        results = self.model(frame, conf=0.6, iou=0.3, verbose=False)
        items = []

        if results and len(results[0].boxes) > 0:
            for box in results[0].boxes:
                cls_id = int(box.cls[0])

                if cls_id == 89:
                    continue  # 오인식 잘되며 불필요한 번호는 데이터 정제작업

                x1, y1, x2, y2 = map(int, box.xyxy[0])

                items.append({
                    'id': cls_id,
                    'name': self.model.names[cls_id],
                    'conf': float(box.conf[0]),
                    'bbox': (x1, y1, x2, y2)
                })

        return items
