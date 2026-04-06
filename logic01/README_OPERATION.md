# 순찰 로봇 시스템 작동 확인 가이드 (Patrol Operation Guide)

이 문서는 순찰 로봇의 안정적인 가동을 위해 권장되는 **단계별 분리 실행** 절차를 설명합니다. 관리 UI에서 맵 패널(Minimap)과 부저 기능이 통합된 최신 버전 기준입니다.

---

## 🧭 빠른 메뉴 (Detailed Guides)
- [SLAM 및 지도 제작 가이드 (README_SLAM.md)](./README_SLAM.md)
- [순찰 스케줄러 및 API 상세 (README_PATROL.md)](./README_PATROL.md)
- [RFID 보정 및 부저 시스템 (README_RFID.md)](./README_RFID.md)

---

## 1. 사전 준비 사항
*   **ROS 2 Humble** 및 필수 의존성 설치
*   **FastAPI 백엔드** 및 **DB** 가동 완결
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

### [Step 1] 순찰 및 스케줄링 실행 (PC)
```bash
source install/setup.bash
ros2 launch patrol_main patrol.launch.py
```

### [Step 2] AI 인식 시스템 실행 (PC)
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
> 이제 부저 기능이 통합되어 UI에서 소리를 낼 수 있습니다.

### [Step 4] 통합 관리용 UI 실행 (PC)
```bash
# 로컬 저장소 상단에서 실행
python3 main.py
```
- **주요 기능**: 실시간 위치 모니터링(Minimap), 부저 비프음 전송, 순찰 간격 설정 등 가능.

---

## 3. 통합 실행 (Total Launch - 간편 모드)
```bash
# 한 번에 실행 (네트워크 안정 시 추천)
ros2 launch patrol_main total_patrol.launch.py use_ai_sim:=false
```

---

## 4. 기능 확인 및 트러블슈팅
*   **RFID 보정**: 로봇이 태그 위를 지날 때 터미널에서 `Landmark Corrected!` 로그 확인.
*   **부저 작동**: UI의 부저 버튼 클릭 시 로봇에서 **3회 비프음** 발생 확인.
*   **코스트맵 정화**: 로봇이 막혔을 경우 아래 명령으로 코스트맵을 초기화하세요.
    ```bash
    ros2 service call /local_costmap/clear_entirely_local_costmap nav2_msgs/srv/ClearEntireCostmap "{}"
    ```

---

 시스템 구성의 전체적인 흐름은 **SJH_backup/SYSTEM_MANAGEMENT_GUIDE.md**를 참고하세요.
