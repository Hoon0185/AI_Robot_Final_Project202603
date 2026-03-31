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
# <ROBOT_IP> 자리에 실제 로봇 IP(예: 192.168.230.78)를 입력하세요.
ssh penguin@<ROBOT_IP> "echo robot123 | sudo -S systemctl stop systemd-timesyncd"

# 2. PC 시간을 로봇에 강제 주입 (PC 터미널에서 실행)
ssh penguin@<ROBOT_IP> "echo robot123 | sudo -S date -s '@$(date +%s)'"

### 💡 시간 차이 확인 방법
로봇과 PC의 시간이 얼마나 차이 나는지 확인하려면 아래 명령어를 사용하세요.
```bash
# 로봇 시간(첫 번째 줄)과 PC 시간(두 번째 줄)을 순서대로 출력
ssh penguin@<ROBOT_IP> "date" && date
```
차이가 1초 이내라면 정상입니다.
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
> 출력되는 `position`의 `x`, `y` 값을 `logic01/src/patrol_main/config/shelf_coords.yaml` 파일의 해당 선반 위치에 입력하세요. (`yaw`는 기본적으로 `0.0`으로 설정해도 무방합니다.)
```

## 5. 맵 저장 및 내비게이션 전환
### A. 맵 저장
```bash
# maps 폴더에서 실행 (파일명 예: my_store_map_01)
ros2 run nav2_map_server map_saver_cli -f ~/my_store_map_01
```

### B. 내비게이션 실행 (순찰 모드)
**주의**: SLAM을 종료(`Ctrl+C`)한 후 실행해야 프레임 충돌이 없습니다.
```bash
# <MAP_NAME>: 저장한 맵 파일 이름 (예: my_store_map_01)
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
  use_sim_time:=false \
  autostart:=true \
  map:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/maps/my_store_map_01.yaml \
  params_file:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/src/patrol_main/config/nav2_params.yaml
```
> [!IMPORTANT]
> 로봇 네임스페이스(예: `TB3_2`)를 사용 중인 경우, 모든 명령어 뒤에 `__ns:=/TB3_2` 옵션을 추가해야 할 수도 있습니다. 
```
> [!TIP]
> 위 명령어는 커스텀 `nav2_params.yaml`을 사용하여 WiFi 지연으로 인한 odom 에러를 방지하고 도착 정밀도를 높였습니다. 실행 후 RViz에서 **[2D Pose Estimate]**로 초기 위치를 잡아주세요.
> 만약 RViz가 자동으로 뜨지 않거나 내비게이션용 설정을 수동으로 불러오고 싶다면 아래 명령어를 별도 터미널에서 실행하세요:
> ```bash
> rviz2 -d $(ros2 pkg prefix turtlebot3_navigation2)/share/turtlebot3_navigation2/rviz/tb3_navigation2.rviz
> ```

## 6. 순찰 시스템 실행
```bash
# 워크스페이스 빌드 및 실행
cd ~/Documents/GitHub/AI_Robot_Final_Project202603/logic01
colcon build --packages-select patrol_main
source install/setup.bash
ros2 launch patrol_main patrol.launch.py
```

### RViz 시각화 (선반 위치 확인)
1. RViz에서 **[Add]** -> **'By topic'** -> `/shelf_markers` (**MarkerArray**) 추가
2. 지도 위에 설정된 선반 위치(초록색 구체)와 이름이 노출됩니다.

### 순찰 시스템의 주요 특징
- **비차단형 지연(Non-blocking Delay)**: 선반 도착 후 2초간 정차할 때 `timer`를 사용하여 노드가 멈추지 않고 상시 통신 가능 상태를 유지합니다.
- **장애 대응(Fault Tolerance)**: 특정 선반으로의 경로가 막혔을 경우, 순찰을 중단하지 않고 자동으로 해당 지점을 건너뛰고(Skipping) 다음 목표로 진행합니다.

## 7. 순찰 스케줄링 및 모드 설정 (CLI vs Python API)
순찰 스케줄러는 실시간으로 파라미터를 변경하여 즉시 적용할 수 있습니다. 터미널 명령(CLI)과 파이썬 코드(API) 중 편한 방법을 사용하세요.

### 모드 1: 주기 순찰 (Periodic)
특정 기준 시점부터 일정한 간격(분 단위)으로 순찰을 반복합니다.

*   **터미널 (CLI)**:
    ```bash
    ros2 param set /patrol_scheduler patrol_mode "periodic"
    ros2 param set /patrol_scheduler patrol_interval_min 60.0
    ros2 param set /patrol_scheduler reference_time "00:00"
    ```
*   **파이썬 (API)**:
    ```python
    patrol.set_patrol_mode("periodic")
    patrol.set_patrol_interval(60.0)
    patrol.set_start_time("00:00")
    ```

### 모드 2: 특정 시각 목록 순찰 (Scheduled)
미리 정의된 시간 목록에 무조건 순찰을 시작합니다.

*   **터미널 (CLI)**:
    ```bash
    ros2 param set /patrol_scheduler patrol_mode "scheduled"
    ros2 param set /patrol_scheduler scheduled_times ["09:00", "13:00", "18:00"]
    ```
*   **파이썬 (API)**:
    ```python
    patrol.set_patrol_mode("scheduled")
    patrol.set_scheduled_times(["09:00", "13:00", "18:00"])
    ```

### 모드 3: 수동 순찰 실행 (Manual Trigger)
스케줄과 상관없이 즉시 순찰을 시작합니다.

*   **터미널 (CLI)**:
    ```bash
    ros2 service call /trigger_manual_patrol std_srvs/srv/Trigger {}
    ```
*   **파이썬 (API)**:
    ```python
    patrol.trigger_manual_patrol()
    ```

## 8. 문제 해결 (Troubleshooting)

### A. 로봇 위치가 안 나타날 때
* **시간 동기화**: 2번 항목을 다시 수행하세요.
* **노드 충돌**: `SLAM`과 `Navigation`이 동시에 켜져 있는지 확인하고 하나만 켜세요.
* **초기 위치**: RViz에서 `2D Pose Estimate`를 다시 찍어주세요.

### B. 맵 로딩 실패 (map_server)
* `my_store_map_01.yaml` 파일 내부의 `image: ...` 경로가 실제 `.pgm` 파일명과 일치하는지 확인하세요. (예: `image: my_store_map_01.pgm`)

### C. 노드 통신 문제 (Namespace)
* 로봇 이름(Namespace)을 사용 중인 경우, `ros2 topic list`를 통해 토픽 이름 앞에 `/TB3_2` 등이 붙어있는지 확인하세요. 붙어 있다면 모든 실행 명령어에 `__ns:=/TB3_2`를 추가해야 합니다.

### D. 순찰 노드 에러
* `shelf_coords.yaml` 파일이 `/**: ros__parameters:` 중첩 구조를 정확히 유지하고 있는지 확인하세요.

### D. 로봇이 움직이지 않고 복구(Recovery)만 반복할 때
주변에 장애물이 없는데도 로봇이 멈춘 경우, 코스트맵에 "유령 장애물"이 남아있을 수 있습니다.
- **해결**: 아래 명령어로 코스트맵을 강제 초기화하세요.
  ```bash
  ros2 service call /local_costmap/clear_entirely_local_costmap nav2_msgs/srv/ClearEntireCostmap "{}"
  ros2 service call /global_costmap/clear_entirely_global_costmap nav2_msgs/srv/ClearEntireCostmap "{}"
  ```

## 9. 순찰 상태 및 시간 정보 (UI 연동)
UI 파트에서 최근 순찰 시간 및 현재 진행 상태를 표시하기 위해 `/patrol_status` 토픽을 제공합니다.

### A. 토픽 정보
- **Topic**: `/patrol_status`
- **Message Type**: `std_msgs/msg/String` (JSON format)

### B. 메시지 형식 예시
- **순찰 중 (patrolling)**:
  ```json
  {
    "status": "patrolling",
    "timestamp": "2026-03-26 09:15:00",
    "start_time": "2026-03-26 09:15:00",
    "current_shelf": "shelf_1",
    "progress": "1/3"
  }
  ```
- **순찰 완료 (completed)**:
  ```json
  {
    "status": "completed",
    "timestamp": "2026-03-26 09:20:00",
    "start_time": "2026-03-26 09:15:00",
    "end_time": "2026-03-26 09:20:00",
    "duration": "00:05:00",
    "total_shelves": 3
  }
  ```

## 10. 파이썬 API 사용 가이드 (PatrolInterface)
UI 파트에서 복잡한 ROS 2 명령어 없이 파이썬 함수 호출만으로 시스템을 제어할 수 있도록 `PatrolInterface` 클래스를 제공합니다.

### A. 기본 사용법
```python
from patrol_main.patrol_interface import PatrolInterface

# 인터페이스 초기화
patrol = PatrolInterface()

# 1. 순찰 모드 설정 ('periodic' 또는 'scheduled')
patrol.set_patrol_mode("periodic")

# 2. 순찰 간격 설정 (분 단위, 예: 30분)
patrol.set_patrol_interval(30.0)

# 3. 주기 순찰 시작 기준 시간 설정 (HH:MM)
patrol.set_start_time("09:00")

# 4. 예약 순찰 시간 목록 설정
patrol.set_scheduled_times(["09:00", "12:00", "15:00", "18:00"])

# 5. 수동 순찰 즉시 실행
patrol.trigger_manual_patrol()

# 6. 최근 순찰 정보(시간, 상태 등) 가져오기
status = patrol.get_recent_patrol_time()
print(f"현재 상태: {status}")

# 작업 완료 후 종료 (필수)
patrol.shutdown()
```

## 11. RFID 랜드마크 보정 가이드 (Robust Localization)
AMCL 위치 추정이 틀어지기 쉬운 환경(대칭형 진열대 등)에서 RFID 태그를 랜드마크로 사용하여 위치를 강제 보정할 수 있습니다.

### A. RFID 노드 활성화
시스템 실행 시 `run_rfid:=true` 인자를 추가합니다.
```bash
ros2 launch patrol_main total_patrol.launch.py run_rfid:=true
```

### B. 보정 원리
1. 로봇 하단의 RFID 리더기가 특정 태그(`landmark_map`에 등록된 ID)를 인식합니다.
2. 인식된 태그에 매핑된 `(x, y, yaw)` 좌표를 기반으로 `PoseWithCovarianceStamped` 메시지를 생성합니다.
3. 생성된 메시지를 `/initialpose` 토픽으로 발행하여 AMCL의 현재 위치를 즉시 업데이트합니다.

### C. 태그 및 좌표 관리
`logic01/src/patrol_main/patrol_main/rfid_localization_node.py` 파일의 `self.landmark_map` 딕셔너리에 태그 ID와 실제 지도상의 좌표를 입력하여 확장할 수 있습니다.

