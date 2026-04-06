import cv2

def main():
    # RTSP URL 설정 (카메라 제조사 및 설정에 따라 다를 수 있습니다)
    # 예: "rtsp://id:pw@192.168.1.18:554/stream1"
    rtsp_url = "rtsp://robot1:robot123@192.168.1.18:554/stream1"

    print(f"Connecting to: {rtsp_url}")
    cap = cv2.VideoCapture(rtsp_url)

    if not cap.isOpened():
        print("Error: Could not open video stream.")
        return

    # 윈도우 이름 설정
    window_name = "RTSP Camera Test (Press 'q' to exit)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to receive frame from stream.")
            break

        # 화면 출력
        cv2.imshow(window_name, frame)

        # 'q' 키를 누르면 종료
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # 자원 해제
    cap.release()
    cv2.destroyAllWindows()
    print("Stream closed.")

if __name__ == "__main__":
    main()
