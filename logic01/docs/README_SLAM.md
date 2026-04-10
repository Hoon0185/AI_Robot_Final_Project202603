# SLAM 및 맵 생성 가이드 (Mapping & SLAM Guide)

이 문서는 순찰 로봇의 **지도 제작(SLAM)** 및 **기본 내비게이션 환경 설정**을 위한 가이드입니다.

---

## 🚀 퀵 링크 (Quick Links)
- [순찰 기동 안내 (README_OPERATION.md)](./README_OPERATION.md)
- [순찰 스케줄링 및 API 상세 가이드 (README_PATROL.md)](./README_PATROL.md)
- [RFID 위치 보정 및 부저 가이드 (README_RFID.md)](./README_RFID.md)

---

## 1. 터틀봇3 기기 연결 및 환경 변수 설정
터틀봇과 PC에서 모두 설정되어 있어야 합니다. (워크스페이스 소스 필수)
```bash
export TURTLEBOT3_MODEL=burger
source ~/turtlebot3_ws/install/setup.bash
```

## 2. 시간 동기화 (필수)
로봇과 PC의 시간이 맞지 않으면 TF 에러로 지도가 그려지지 않거나 로봇 위치가 사라집니다.

### A. 인터넷 기반 자동 동기화 (권장)
로봇에 인터넷이 연결되어 있다면 `chrony`를 사용하는 것이 가장 확실합니다.
```bash
ssh penguin@<ROBOT_IP>
sudo systemctl start chrony
sudo systemctl enable chrony
# 동기화 상태 확인
chronyc tracking
```

### B. PC 시간을 로봇에 강제 주입 (임시 방편)
인터넷이 안 되는 환경에서 PC 시간을 로봇에 복사합니다.
```bash
# 1. 로봇(SSH)에서 자동 동기화 중지
ssh penguin@<ROBOT_IP> "echo robot123 | sudo -S systemctl stop systemd-timesyncd"

# 2. PC 시간을 로봇에 강제 주입 (PC 터미널에서 실행)
ssh penguin@<ROBOT_IP> "echo robot123 | sudo -S date -s '@$(date +%s)'"
```

---

## 3. 로봇 기체 실행 (Bringup)
로봇 본체(라즈베리 파이) 터미널에서 실행합니다.
```bash
ros2 launch turtlebot3_bringup robot.launch.py
```

## 4. SLAM 및 좌표 추출
### A. SLAM 실행 (PC)
```bash
ros2 launch slam_toolbox online_async_launch.py use_sim_time:=false
```

### B. 로봇 수동 조작 (PC)
로봇을 움직여 지도를 완성합니다. 별도의 터미널(PC)에서 실행합니다.
```bash
ros2 run turtlebot3_teleop teleop_keyboard
```

### C. 선반 좌표 추출 (Publish Point)
RViz 상단의 **[Publish Point]** 도구를 클릭하고 지도 위 선반 위치를 찍으세요. 터미널(PC)에서 아래 명령어로 좌표를 확인합니다.
```bash
ros2 topic echo /clicked_point
```
> [!NOTE]
> 출력되는 `position`의 `x`, `y` 값을 `logic01/src/patrol_main/config/shelf_coords.yaml` 파일의 해당 선반 위치에 입력하세요.

---

## 5. 맵 저장 및 내비게이션 전환
### A. 맵 저장
```bash
# maps 폴더에서 실행 (파일명 예: my_store_map_01)
ros2 run nav2_map_server map_saver_cli -f ~/my_store_map_01
```

### B. 내비게이션 실행 (기본 모드)
**주의**: SLAM을 종료(`Ctrl+C`)한 후 실행해야 프레임 충돌이 없습니다.
단독 실행보다 **`total_patrol.launch.py`**를 통한 실행이 경로 자동 치환 로직 덕분에 훨씬 안정적이며 권장됩니다.

```bash
# 수동 실행 시 (경로 확인 필수)
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
  use_sim_time:=false \
  autostart:=true \
  map:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/maps/my_store_map_02.yaml \
  params_file:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/src/patrol_main/config/nav2_params.yaml \
  cmd_vel:=cmd_vel_nav
```
> [!IMPORTANT]
> 수동 실행 시 `cmd_vel:=cmd_vel_nav` 리매핑을 반드시 포함해야 장애물 회피 멀티플렉서가 작동합니다.

---

## 6. 트러블슈팅 (SLAM/Map)

### A. 로봇 위치가 안 나타날 때
- **시간 동기화**: 2번 항목을 다시 수행하세요.
- **노드 충돌**: `SLAM`과 `Navigation`이 동시에 켜져 있는지 확인하고 하나만 켜세요.
- **초기 위치 (Initial Pose)**: **[중요]** 최신 버전에서는 "Auto Init(0,0,0)" 기능이 제거되었습니다. RViz의 `2D Pose Estimate`를 클릭하여 실제 로봇의 위치와 방향을 지도 상에 정확히 찍어주어야 내비게이션이 동작합니다.

### B. 맵 로딩 실패 (map_server)
- `my_store_map_02.yaml` 파일 내부의 `image: ...` 경로가 실제 `.pgm` 파일명과 일치하는지 확인하세요.

---

 더 자세한 순찰 제어 및 RFID 보정 방법은 각각 **README_PATROL.md**와 **README_RFID.md**를 참고하세요. (전체 관리 흐름은 **../../SJH_backup/SYSTEM_MANAGEMENT_GUIDE.md** 참고)

