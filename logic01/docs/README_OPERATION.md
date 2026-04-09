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
*   **FastAPI 백엔드** 및 **DB** 가동 완료 (PC DB 포트 **8000** 표준 직접 연결 확인)
*   터틀봇3와 PC 간의 **시간 동기화** (`chrony`) 완료

---

## 2. 단계별 실행 절차 (권장: 분리 실행)

### [Step 0] 내비게이션 및 맵 실행 (PC)
```bash
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
  use_sim_time:=false \
  autostart:=true \
  map:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/maps/my_store_map_02.yaml \
  params_file:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/src/patrol_main/config/nav2_params.yaml \
  cmd_vel:=cmd_vel_nav
```

### [Step 1] 순찰 및 장애물 회피 실행 (PC)
- `patrol_main` 패키지로 통합된 장애물 회피 노드가 포함된 통합 순찰 런치를 실행합니다.
- **중요**: 소스 코드를 수정했다면 반드시 빌드 후 실행해야 합니다.
```bash
colcon build --symlink-install --packages-select patrol_main
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

## 3. 통합 실행 (Total Launch - 가장 권장됨)
- **`total_patrol.launch.py`**는 Python 기반의 **가변 경로 자동 치환 로직**을 통해 설정 파일 내의 `replace_at_runtime` 표시자를 실행 시점에 로컬 환경의 절대 경로로 강제 수정합니다. 
- 환경에 구애받지 않고 모든 노드(Nav2, Patrol, AI 등)를 한 번에 안정적으로 실행할 수 있는 최선의 방법입니다.

```bash
# 한 번에 실행 (네트워크 안정 시 추천)
ros2 launch patrol_main total_patrol.launch.py use_ai_sim:=false run_obstacle_node:=true
```

### [옵션] 장애물 노드 비활성화
장애물 회피 로직의 간섭 없이 순수 성능을 테스트하고 싶다면 아래 옵션으로 시작하거나, 런타임에 끌 수 있습니다.
*   **시작 시 노드 제외**: `run_obstacle_node:=false` 추가
*   **실행 중 로직 비활성화**:
    ```bash
    ros2 param set /obstacle_node use_obstacle_avoidance false
    ```

---

*   **빌드 누락 주의**: 코드를 수정했는데도 예전 에러 로그가 계속 뜬다면, `colcon build --symlink-install` 명령어가 빠지지 않았는지 확인하세요.
*   **순찰 중단 로그 추적**: 순찰이 갑자기 멈춘다면 터미널 로그에서 **`[상태 변경] ...`**으로 시작하는 메시지를 찾으세요. 시스템이 순찰을 종료한 구체적인 원인(긴급 정지, 복귀 명령, 주행 실패 등)을 즉시 알 수 있습니다.
*   **Aborted(6) 발생 시**: 장애물 회피 중 Preemption에 의해 Aborted가 발생해도 현재의 로봇은 순찰을 종료하지 않고 2초 대기 후 자동으로 목표를 재전송하여 주행을 재개합니다.
*   **지능형 장애물 인식 (Virtual Wall)**: 로봇이 주행 중 멈춰있다면 `ros2 topic echo /scan_virtual`을 확인하세요. Nav2가 장애물을 인식하여 우회 경로를 생성하도록 돕는 가짜 벽 정보가 발행되고 있는지 볼 수 있습니다.
*   **카메라 지연(Cam Delay) 대응**: 현재 시스템은 누적 버퍼 클리어 로직이 적용되었습니다. 화면 지연이 누적된다면 'Buffer Skip' 로그가 발생하는지 확인하세요.
*   **주행 민감도 조정 (sim_time)**: 로봇이 너무 소극적으로 움직이면 `nav2_params.yaml`의 `sim_time`을 조정하세요 (현재 권장값 `1.5`).
*   **코스트맵 정화**: 로봇이 유령 장애물에 갇혔을 경우 아래 명령으로 코스트맵을 초기화하세요.
    ```bash
    ros2 service call /local_costmap/clear_entirely_local_costmap nav2_msgs/srv/ClearEntireCostmap "{}"
    ```

---

 시스템 구성의 전체적인 흐름은 **docs/notion_records/** 내부의 문서를 참고하세요.
