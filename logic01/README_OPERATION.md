# 순찰 로봇 시스템 작동 확인 가이드 (Patrol Operation Guide)

이 문서는 완성된 순찰 로봇의 로직과 UI 통합 시스템이 정상적으로 작동하는지 확인하기 위한 절차를 설명합니다.

---

## 1. 사전 준비 사항
시스템을 실행하기 전에 다음 환경이 준비되어 있어야 합니다.

*   **ROS 2 Humble**: 로봇 제어 및 통신을 위해 필요합니다.
*   **FastAPI 백엔드**: 재고 데이터 및 알림 처리를 위해 실행 중이어야 합니다 (기본 포트: 8000).
*   **Navigation2 Stack**: 순찰 및 복귀 기능을 위해 반드시 실행 중이어야 합니다.
*   **의존성**: `PyQt6`, `requests`, `rclpy`, `nav2_msgs`, `uvicorn` 등이 설치되어 있어야 합니다.

---

## 2. 시스템 실행 순서

각 단계는 별도의 터미널에서 실행하는 것을 권장합니다.

### 0단계: 내비게이션 및 맵 실행 (Nav2)
순찰 및 복귀 기능이 정상적으로 작동하려면 먼저 내비게이션 스택과 맵이 로드되어 있어야 합니다.
```bash
# 터미널 1: 내비게이션 실행
# <MAP_NAME> 자리에 저장한 맵 파일 이름을 입력하세요.
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
  use_sim_time:=false \
  autostart:=true \
  map:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/maps/my_store_map_01.yaml \
  params_file:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/src/patrol_main/config/nav2_params.yaml
```

### 1단계: ROS 2 환경 설정 및 노드 실행
먼저 ROS 2 워크스페이스를 빌드하고 순찰 시스템(스케줄러, 메인 노드 등)을 실행합니다.
```bash
# 워크스페이스 루트에서 실행
colcon build --packages-select patrol_main
source install/setup.bash

# 순찰 전체 시스템 실행 (스케줄러 포함)
ros2 launch patrol_main patrol.launch.py
```

### 2단계: FastAPI 백엔드 서버 실행
재고 데이터 동기화 및 알림 기능을 위해 백엔드 서버를 먼저 실행합니다.
```bash
# 리포지토리 루트에서 실행
cd web-server
pip install -r requirements.txt  # 최초 실행 시 의존성 설치
uvicorn main:app --reload --port 8000
```

### 3단계: 관리용 UI 실행 (PyQt6)
로봇을 제어하고 상태를 모니터링할 UI를 실행합니다.
```bash
# 리포지토리 루트에서 실행 (새 터미널)
python3 main.py
```

---

## 3. 기능별 작동 확인 방법

### 🕹️ 수동 조작 및 비상 정지
1.  UI에서 **"🕹 수동 조작 버튼"**을 클릭하여 조작 모드로 진입합니다.
2.  **방향키(▲, ▼, ◀, ▶)**를 눌러 로봇의 이동 명령을 시뮬레이션합니다.
    *   터미널 로그에 `[LOGIC] 수동 이동: UP/DOWN...` 메시지가 출력되는지 확인하십시오.
3.  **"🚨 비상정지"** 버튼을 클릭합니다.
    *   로봇의 현재 이동 명령이 즉시 중단되는지 확인하십시오.

### 🗄️ 재고 DB 및 알림 조회
1.  메인 화면에서 **"🗄 DB 조회 버튼"**을 클릭합니다.
    *   FastAPI 서버로부터 최신 재고 데이터를 가져와 테이블에 표시하는지 확인하십시오.
2.  **"🔔 재고 알림 버튼"**을 클릭합니다.
    *   서버에서 판단한 '재고 부족' 물품 리스트가 정상적으로 로드되는지 확인하십시오.

### 🔄 순찰 복귀 (Return to Base)
1.  수동 조작 모드 또는 팝업에서 **"🔄 순찰복귀"** 또는 **"초기 위치 버튼"**을 클릭합니다.
    *   로봇이 맵의 원점 `(0.0, 0.0)` 좌표를 목표로 이동을 시작하는지 확인하십시오 (RViz 등으로 확인 가능).

### 📡 실시간 상태 모니터링
1.  UI 상단의 **"🗓 마지막 순찰 시간"** 영역을 확인합니다.
2.  순찰이 시작되면 `(순찰 중: shelf_1 1/4)`와 같은 형식으로 실시간 진행 상태가 업데이트되는지 확인하십시오.

---

## 4. 트러블슈팅

*   **UI 실행 시 에러 발생**: `robot_logic.py`에서 `patrol_interface` 임포트 경로가 올바른지 확인하십시오.
*   **데이터가 비어있음**: FastAPI 서버가 작동 중인지, `InventoryDB`의 `base_url`이 정확한지 확인하십시오.
*   **명령어가 전달되지 않음**: ROS 2 노드들이 동일한 `ROS_DOMAIN_ID`를 사용하는지, 혹은 통신 환경(Namespace 등)이 일치하는지 확인하십시오.
