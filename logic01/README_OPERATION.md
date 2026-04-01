# 순찰 로봇 시스템 작동 확인 가이드 (Patrol Operation Guide)

이 문서는 완성된 순찰 로봇의 로직과 UI 통합 시스템이 정상적으로 작동하는지 확인하기 위한 절차를 설명합니다.

---

## 1. 사전 준비 사항
시스템을 실행하기 전에 다음 환경이 준비되어 있어야 합니다.

*   **ROS 2 Humble**: 로봇 제어 및 통신을 위해 필요합니다.
*   **FastAPI 백엔드**: 재고 데이터 및 알림 처리를 위해 실행 중이어야 합니다 (기본 포트: 8000).
*   **Navigation2 Stack**: 순찰 및 복귀 기능을 위해 반드시 실행 중이어야 합니다.
*   **의존성**: `PyQt6`, `requests`, `rclpy`, `nav2_msgs`, `uvicorn`, `ultralytics`, `opencv-python` 등이 설치되어 있어야 합니다.
*   **시간 동기화 (Chrony)**: 터틀봇과 PC 간의 시스템 시간이 일치해야 TF 에러가 발생하지 않습니다. (SLAM 가이드 참고)

---

## 2. 시스템 실행 순서

### 가단계: 모든 시스템 일괄 실행 (Total Launch)
내비게이션과 순찰 노드, AI 인식 노드들을 하나의 명령어로 일괄 실행합니다.

```bash
# 워크스페이스 루트에서 실행
colcon build --packages-select patrol_main logic2_pkg protect_product protect_product_msgs
source install/setup.bash

# 터미널 1: 모든 시스템 일괄 실행
# [기본 실행 - 실제 카메라 사용]
ros2 launch patrol_main total_patrol.launch.py

# [시뮬레이션 - 카메라 미연결 또는 테스트 시] 
ros2 launch patrol_main total_patrol.launch.py use_ai_sim:=true
```

### 나단계: 관리용 UI 실행 (PyQt6)
로봇을 제어하고 상태를 모니터링할 UI를 실행합니다.
```bash
# 리포지토리 루트에서 실행 (새 터미널)
python3 main.py
```

---

## 3. 기능별 작동 확인 방법

### 🕹️ 수동 조작 및 비상 정지
1.  UI에서 **"🕹 수동 조작 버튼"**을 클릭하여 조작 모드로 진입합니다.
2.  **방향키**를 눌러 로봇이 이동하는지 확인합니다.
3.  **"🚨 비상정지"** 버튼 클릭 시 모든 동작이 즉시 멈추는지 확인합니다.

### 🤖 AI 물품 인식 및 실시간 리포팅
1.  순찰 중 선반 도착 시 로봇이 **8초간** 정지하여 스캔을 수행합니다.
2.  **모니터링**: `ros2 run rqt_image_view rqt_image_view`를 실행하고 `/verif_img/compressed` 토픽을 확인합니다.
    *   YOLO가 물체를 탐지하고 바코드를 대조하여 `[OK]` 또는 `[ERR]` 표시가 나타나는지 확인합니다.
3.  인식 결과는 즉시 서버 DB로 전송되며, UI의 재고 리스트에 반영됩니다.

### 📡 로봇 상태 및 하트비트 모니터링
1.  UI 상단 상태바에 로봇의 실시간 위치와 상태(`IDLE`, `PATROLLING`, `SCANNING`)가 표시되는지 확인합니다.
2.  로봇 노드가 종료되거나 통신이 끊기면 UI에 `[OFFLINE]` 표시가 나타나는지 확인합니다.

---

## 4. 트러블슈팅

*   **AI 노드 실행 실패**: `protect_product` 패키지가 정상적으로 빌드되었는지 확인하세요. (`detector_node`, `verifier_node` 이름 확인)
*   **DB 연결 실패**: 서버(`http://16.184.56.119`) 접속 가능 여부를 확인하세요.
*   **네비게이션 에러**: `nav2_params.yaml` 경로와 맵 파일 존재 여부를 확인하세요.
*   **시간 동기화 문제**: 터틀봇과 PC의 시간이 일치하지 않으면 내비게이션이 작동하지 않습니다. `chrony` 설정을 확인하세요.
