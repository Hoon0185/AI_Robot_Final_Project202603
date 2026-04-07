# 순찰 로봇 시스템 작동 확인 가이드 (Patrol Operation Guide)

이 문서는 순찰 로봇의 안정적인 가동을 위해 권장되는 **단계별 분리 실행** 절차를 설명합니다. 관리 UI에서 맵 패널(Minimap) 서버 동기화와 실시간 설정 반영(`RECONFIG`) 기능이 통합된 최신 버전 기준입니다.

---

## 🧭 빠른 메뉴 (Detailed Guides)
- [SLAM 및 지도 제작 가이드 (README_SLAM.md)](./README_SLAM.md)
- [순찰 스케줄러 및 API 상세 (README_PATROL.md)](./README_PATROL.md)
- [RFID 보정 및 부저 시스템 (README_RFID.md)](./README_RFID.md)

---

## 1. 사전 준비 사항
*   **ROS 2 Humble** 및 필수 의존성 설치
*   **FastAPI 백엔드** 및 **DB** 가동 완료 (PC DB 포트 **8000** 직접 연결 확인)
*   터틀봇3와 PC 간의 **시간 동기화** (`chrony`) 완료

---

## 2. 단계별 실행 절차 (권장: 분리 실행)

### [Step 0] 내비게이션 및 맵 실행 (PC)
```bash
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
  use_sim_time:=false \
  autostart:=true \
  map:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/maps/my_store_map_01.yaml \
  params_file:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/src/patrol_main/config/nav2_params.yaml \
  cmd_vel:=cmd_vel_nav
```

### [Step 1] 순찰 및 장애물 회피 실행 (PC)
- `patrol_main` 패키지로 통합된 장애물 회피 노드가 포함된 통합 순찰 런치를 실행합니다.
```bash
source install/setup.bash
colcon build --packages-select patrol_main protect_product_msgs protect_product
source install/setup.bash
ros2 launch patrol_main patrol.launch.py
```

### [Step 2] AI 인식 시스템 실행 (PC)
- `protect_product` 패키지를 통해 YOLO 기반 상품 인식을 수행합니다.
```bash
# 실제 카메라 사용 시
ros2 launch protect_product ai_detection.launch.py
# 시뮬레이션 모드 사용 시
ros2 launch protect_product ai_detection.launch.py use_ai_sim:=true
```

### [Step 3] RFID 및 부저 노드 실행 (Robot - SSH)
```bash
ssh penguin@192.168.0.3
cd ~/rfid
python3 standalone_rfid_buzzer.py
```
> [!TIP]
> 부저 기능이 통합되어 UI의 '부저' 버튼 클릭 시 즉시 3회 비프음이 발생합니다.

### [Step 4] 통합 관리용 UI 실행 (PC)
```bash
# 로컬 저장소 상단에서 실행
python3 main.py
```
- **실시간 좌표 연동**: UI 미니맵의 로봇 마커는 서버에 기록되는 `last_odom_x/y` 좌표와 실시간 동기화됩니다.
- **실시간 설정 반영**: UI에서 장애물 대기 시간을 변경하고 [확인]을 누르면, 로봇이 즉시 `RECONFIG` 신호를 받아 설정을 갱신합니다.

---

## 3. 통합 실행 (Total Launch - 간편 모드)
```bash
# 한 번에 실행 (네트워크 안정 시 추천)
ros2 launch patrol_main total_patrol.launch.py use_ai_sim:=false
```

---

## 4. 기능 확인 및 트러블슈팅
*   **서버 동기화**: `patrol_node` 실행 시 최초 한 번 서버 설정을 가져오면 주기적 Polling을 중단하고 이벤트 기반(순찰 시작 전/RECONFIG 수신 시)으로 동작합니다.
*   **미니맵 마커**: 로봇이 움직이는데 미니맵 마커가 고정되어 있다면 백엔드 서버(8000번 포트)의 `/patrol/list` 응답을 확인하세요.
*   **코스트맵 정화**: 로봇이 막혔을 경우 아래 명령으로 코스트맵을 초기화하세요.
    ```bash
    ros2 service call /local_costmap/clear_entirely_local_costmap nav2_msgs/srv/ClearEntireCostmap "{}"
    ```

---

 시스템 구성의 전체적인 흐름은 **docs/notion_records/** 내부의 문서를 참고하세요.
