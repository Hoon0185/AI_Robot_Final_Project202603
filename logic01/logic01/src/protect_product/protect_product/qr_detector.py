import cv2
from pyzbar.pyzbar import decode

class QRDetector:
    def __init__(self):
        pass

    def detect(self, frame):
        # [1] 전처리: 그레이스케일 -> 선명화
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # [2] 이진화 처리 - 블러로 노이즈 제거 및 이진화
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # [3] 디코딩 (전처리 된 이미지 혹은 원본으로 QR읽기)
        objs = decode(thresh) or decode(gray)

        # 도출 결과 저장
        results = []
        for obj in objs:
            l, t, w, h = obj.rect
            results.append({
                'text': obj.data.decode('utf-8').strip(),#QR 텍스트 저장
                'bbox': (l, t, l+w, t+h) #QR인식된 영역 저장
            })
        return results
