import cv2
try:
    from pyzbar.pyzbar import decode
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False

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
        if not PYZBAR_AVAILABLE:
            # 의존성 부재 시 경고 출력 후 빈 결과 반환
            print("WARNING [QR]: pyzbar module not found. QR detection skipped.")
            return []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 여러 기법을 병합하여 인식률 향상
        objs = decode(gray)  # 1. 일반 그레이스케일 시도 (가장 안정적)
        if not objs:
            objs = decode(thresh) # 2. 안 되면 이진화 데이터 시도
        if not objs:
            # 3. 대비 강화 후 시도
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            contrast = clahe.apply(gray)
            objs = decode(contrast)
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
