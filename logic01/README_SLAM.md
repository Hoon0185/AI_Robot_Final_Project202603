# SLAM 및 맵 생성 가이드 (메인 로직01용)

CyCle03(메인 로직01)이 담당하는 SLAM 및 맵 생성을 위한 절차입니다. 터틀봇3 기준 명령어입니다.

## 1. 터틀봇3 기기 연결 및 환경 변수 설정
터틀봇과 PC에서 모두 설정되어 있어야 합니다. (워크스페이스 소스 필수)
```bash
export TURTLEBOT3_MODEL=burger
source ~/turtlebot3_ws/install/setup.bash
```

## 2. 시간 동기화 (필수)
로봇과 PC의 시간이 맞지 않으면 TF 에러로 지도가 그려지지 않거나 로봇 위치가 사라집니다.
```bash
# 1. 로봇(SSH)에서 자동 동기화 중지
ssh penguin@192.168.1.201 "echo robot123 | sudo -S systemctl stop systemd-timesyncd"

# 2. PC 시간을 로봇에 강제 주입 (PC 터미널에서 실행)
ssh penguin@192.168.1.201 "echo robot123 | sudo -S date -s '@$(date +%s)'"
```

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

### B. 선반 좌표 추출 (Publish Point)
RViz 상단의 **[Publish Point]** 도구를 클릭하고 지도 위 선반 위치를 찍으세요. 터미널(PC)에서 아래 명령어로 좌표를 확인합니다.
```bash
ros2 topic echo /clicked_point
```

## 5. 맵 저장 및 내비게이션 전환
### A. 맵 저장
```bash
# maps 폴더에서 실행 (파일명: my_map_03)
ros2 run nav2_map_server map_saver_cli -f ~/my_map_03
```

### B. 내비게이션 실행 (순찰 모드)
**주의**: SLAM을 종료(`Ctrl+C`)한 후 실행해야 프레임 충돌이 없습니다.
```bash
ros2 launch turtlebot3_navigation2 navigation2.launch.py use_sim_time:=false autostart:=true map:=/절대경로/my_map_03.yaml
```
* **Tip**: 실행 후 RViz에서 **[2D Pose Estimate]**로 로봇의 초기 위치를 반드시 찍어주세요.

## 6. 순찰 시스템 실행
```bash
# 워크스페이스 빌드 및 실행
colcon build --packages-select patrol_main
source install/setup.bash
ros2 launch patrol_main patrol.launch.py
```

### RViz 시각화 (선반 위치 확인)
1. RViz에서 **[Add]** -> **'By topic'** -> `/shelf_markers` (**MarkerArray**) 추가
2. 지도 위에 설정된 선반 위치(초록색 구체)와 이름이 노출됩니다.

## 7. 순찰 스케줄링 및 모드 설정 (Dynamic Parameter)
순찰 스케줄러는 실시간으로 파라미터를 변경하여 즉시 적용할 수 있습니다.

### 모드 1: 주기 순찰 (Periodic)
특정 기준 시점부터 일정한 간격(분 단위)으로 순찰을 반복합니다.
```bash
# 모드 설정
ros2 param set /patrol_scheduler patrol_mode "periodic"
# 간격 설정 (예: 60분 간격)
ros2 param set /patrol_scheduler patrol_interval_min 60.0
# 기준 시점 설정 (HH:MM 형식)
ros2 param set /patrol_scheduler reference_time "00:00"
```

### 모드 2: 특정 시각 목록 순찰 (Scheduled)
미리 정의된 시간 목록에 무조건 순찰을 시작합니다.
```bash
# 모드 설정
ros2 param set /patrol_scheduler patrol_mode "scheduled"
# 순찰 시각 목록 설정
ros2 param set /patrol_scheduler scheduled_times ["09:00", "13:00", "18:00"]
```

### 모드 3: 수동 순찰 실행 (Manual Trigger)
스케줄과 상관없이 UI 또는 터미널에서 즉시 순찰을 시작합니다.
```bash
# 터미널에서 즉시 순찰 시작 명령
ros2 service call /trigger_manual_patrol std_srvs/srv/Trigger {}
```

## 8. 문제 해결 (Troubleshooting)

### A. 로봇 위치가 안 나타날 때
* **시간 동기화**: 2번 항목을 다시 수행하세요.
* **노드 충돌**: `SLAM`과 `Navigation`이 동시에 켜져 있는지 확인하고 하나만 켜세요.
* **초기 위치**: RViz에서 `2D Pose Estimate`를 다시 찍어주세요.

### B. 맵 로딩 실패 (map_server)
* `my_map_03.yaml` 파일 내부의 `image: ...` 경로가 실제 `.pgm` 파일명과 일치하는지 확인하세요.

### C. 순찰 노드 에러
* `shelf_coords.yaml` 파일이 `/**: ros__parameters:` 중첩 구조를 유지하고 있는지 확인하세요.

### D. 로봇이 움직이지 않고 복구(Recovery)만 반복할 때
주변에 장애물이 없는데도 로봇이 멈춘 경우, 코스트맵에 "유령 장애물"이 남아있을 수 있습니다.
- **해결**: 아래 명령어로 코스트맵을 강제 초기화하세요.
  ```bash
  ros2 service call /local_costmap/clear_entirely_local_costmap nav2_msgs/srv/ClearEntireCostmap "{}"
  ros2 service call /global_costmap/clear_entirely_global_costmap nav2_msgs/srv/ClearEntireCostmap "{}"
  ```
