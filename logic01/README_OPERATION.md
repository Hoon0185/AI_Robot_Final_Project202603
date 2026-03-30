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
# 터미널 1: 내비게이션 실행 (cmd_vel을 cmd_vel_nav로 리맵핑하여 멀티플렉서에 연결)
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
  use_sim_time:=false \
  autostart:=true \
  map:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/maps/my_store_map_01.yaml \
  params_file:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/src/patrol_main/config/nav2_params.yaml \
  cmd_vel:=cmd_vel_nav
```

### 1단계: ROS 2 환경 설정 및 노드 실행
먼저 ROS 2 워크스페이스를 빌드하고 전체 시스템을 실행합니다. 기본적으로 네임스페이스 없이 실행되지만, 팀 프로젝트 등 하드웨어 환경에 따라 네임스페이스가 필요한 경우 `namespace:=이름` 인자를 추가할 수 있습니다.

```bash
# 워크스페이스 루트에서 실행
colcon build --packages-select patrol_main logic2_pkg
source install/setup.bash

# 터미널 2: 전체 순찰 시스템 실행 (순찰 로직 + 장애물 회피 + 멀티플렉서)
# [기본] ros2 launch patrol_main total_patrol.launch.py
# [네임스페이스 사용 시] ros2 launch patrol_main total_patrol.launch.py namespace:=TB3_2
ros2 launch patrol_main total_patrol.launch.py
```

### 2단계: 백엔드 서버 상태 확인 (Remote)
데이터 동기화 및 알림 기능을 위해 원격 서버(`http://16.184.56.119`)가 작동하고 있어야 합니다. 로봇과 PC가 해당 IP에 접속 가능한 네트워크에 있는지 확인하세요.
*(로컬 서버를 직접 실행할 필요는 없으나, 필요한 경우 `web-server` 폴더에서 `uvicorn`으로 실행할 수 있습니다.)*

### 3단계: 관리용 UI 실행 (PyQt6)
로봇을 제어하고 상태를 모니터링할 UI를 실행합니다.
```bash
# 리포지토리 루트에서 실행 (새 터미널)
# [기본] python3 main.py
# [네임스페이스 사용 시] python3 main.py --ros-args --remap __ns:=/TB3_2
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

### 📡 원격 대시보드 명령 (Remote Dashboard)
1.  **웹 브라우저**에서 `http://16.184.56.119/` (또는 서버 IP)에 접속합니다.
2.  대시보드 상단의 **[순찰 개시]** 또는 **[비상 정지]** 버튼을 클릭합니다.
3.  로봇 UI 터미널에 `[REMOTE] New command received: ...` 로그가 출력되며 로봇이 즉시 자율 순찰을 시작하거나 멈추는지 확인하십시오. (약 2초 이내 반응)

---

## 4. 원격 서버 데이터베이스 관리 (Server branch 도구)
`web-server` 디렉토리에는 시스템 초기 구축 및 관리를 위한 도구들이 포함되어 있습니다.

### 4.1 기초 데이터 입력 (최초 1회 필수)
새로운 환경에서 DB를 구축하거나 테이블을 초기화하려면 다음 명령을 실행합니다.
```bash
cd web-server
python3 insert_base_data.py
```
*   `product_master`, `waypoint`, `waypoint_product_plan` 등을 자동으로 세팅합니다.

### 4.2 수동 재고 관리 CLI
로봇 순찰 외에 사람이 직접 입/출고를 관리할 때 사용하는 도구입니다.
```bash
python3 inventory_manager.py
```
*   메뉴에서 1:입고, 2:출고를 선택하고 상품 ID와 수량을 입력하여 즉시 DB에 반영할 수 있습니다.

---

## 5. 트러블슈팅

*   **UI 실행 시 에러 발생**: `robot_logic.py`에서 `patrol_interface` 임포트 경로가 올바른지 확인하십시오.
*   **데이터가 비어있음**: FastAPI 서버가 작동 중인지, `InventoryDB`의 `base_url`이 정확한지 확인하십시오.
*   **명령어가 전달되지 않음**: ROS 2 노드들이 동일한 `ROS_DOMAIN_ID`를 사용하는지, 혹은 통신 환경(Namespace 등)이 일치하는지 확인하십시오.
*   **패키지 누락**: `pip install mysql-connector-python requests` 명령이 수행되었는지 확인하십시오.
