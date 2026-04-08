import cv2
from pyzbar.pyzbar import decode

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

class QRDetector:
    def __init__(self):
        pass

    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        objs = decode(thresh) or decode(gray)
        results = []

        for obj in objs:
            l, t, w, h = obj.rect

            # 객체 생성 방식으로 변경
            qr = DetectionResult(
                box=[l, t, l+w, t+h],
                class_name="QR_CODE",
                raw_data=obj.data.decode('utf-8').strip()
            )

            # 리스트에 넣기 전 확인 로그
            print(f"DEBUG [QR]: {qr.raw_data} 인식됨")
            results.append(qr)

        return results
