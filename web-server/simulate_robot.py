import requests
import json
from datetime import datetime
import time

# 서버 주소 (FastAPI 포트: 8000)
SERVER_URL = "http://localhost:8000/detections/add"
RESOLVE_URL = "http://localhost:8000/alerts"

def send_detection(tag, detected, confidence=0.98):
    payload = {
        "tag_barcode": tag,
        "detected_barcode": detected,
        "confidence": confidence,
        "odom_x": 1.23,
        "odom_y": 4.56,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(SERVER_URL, json=payload)
        print(f"\n[전송] 태그: {tag}, 인식상품: {detected if detected else '없음'}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"[응답] 상태: {result.get('status')}")
            print(f"[판독 결과] {result.get('judgment')}")
            print(f"[위치 정보] {result.get('location')} (태그: {result.get('tag_barcode')})")
        else:
            print(f"❌ 서버 오류: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ 전송 실패: {e}")

def run_menu():
    print("="*30)
    print("🤖 Gilbot 가상 로봇 시뮬레이터")
    print("="*30)
    print("1. [정상] 신라면 매대(8801111222233)에서 신라면(8801111222233)을 인식한 경우")
    print("2. [없음] 신라면 매대(8801111222233)에서 아무것도 감지되지 않은 경우")
    print("3. [오진열] 신라면 매대(8801111222233)에서 초코에몽(8801111999999)이 발견된 경우")
    print("4. [오진열] 신라면 매대(8801111222233)에서 불닭볶음면(8801111555555)이 발견된 경우")
    print("5. [해결] 미해결 알림 목록 조회 및 조치 완료 처리")
    print("q. 종료")
    print("-" * 30)

    while True:
        choice = input("\n원하는 시나리오 번호를 선택하세요: ").strip().lower()
        
        if choice == '1':
            send_detection("8801111222233", "8801111222233", 0.99)
        elif choice == '2':
            send_detection("8801111222233", None, 0.0)
        elif choice == '3':
            send_detection("8801111222233", "8801111999999", 0.95)
        elif choice == '4':
            send_detection("8801111222233", "8801111555555", 0.92)
        elif choice == '5':
            # 미해결 알림 목록 조회
            try:
                res = requests.get(RESOLVE_URL)
                if res.status_code == 200:
                    alerts = res.json()
                    if not alerts:
                        print("현재 처리할 미해결 알림이 없습니다.")
                        continue
                    
                    print("\n--- 미해결 알림 목록 ---")
                    for i, a in enumerate(alerts):
                        print(f"{i+1}. ID:{a['alert_id']} | 타입:{a['alert_type']} | 메시지:{a['message']}")
                    
                    idx_str = input("\n해결 처리할 번호를 선택하세요 (취소:c): ").strip()
                    if idx_str.lower() == 'c': continue
                    
                    idx = int(idx_str) - 1
                    target_id = alerts[idx]['alert_id']
                    
                    # 해결 요청
                    solve_res = requests.post(f"{RESOLVE_URL}/{target_id}/resolve")
                    if solve_res.status_code == 200:
                        print(f"✅ 알림 {target_id}번이 성공적으로 해결 처리되었습니다.")
                    else:
                        print(f"❌ 실패: {solve_res.text}")
                else:
                    print(f"❌ 알림 목록 조회 실패: {res.status_code}")
            except Exception as e:
                print(f"❌ 오류 발생: {e}")
        elif choice == 'q':
            print("시뮬레이터를 종료합니다.")
            break
        else:
            print("❌ 잘못된 선택입니다. 다시 입력해 주세요.")

if __name__ == "__main__":
    run_menu()
