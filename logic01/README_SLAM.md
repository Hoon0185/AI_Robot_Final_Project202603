# SLAM 및 맵 생성 가이드 (메인 로직01용)

CyCle03(메인 로직01)이 담당하는 SLAM 및 맵 생성을 위한 절차입니다. 터틀봇3 기준 명령어입니다.

## 1. 터틀봇3 기기 연결 및 환경 변수 설정
터틀봇과 PC에서 모두 설정되어 있어야 합니다.
```bash
export TURTLEBOT3_MODEL=burger  # 또는 waffle_pi
```

## 2. 로봇 기체 실행 (Bringup)
로봇 본체(라즈베리 파이) 터미널에서 실행합니다. 센서와 모터를 활성화하는 필수 단계입니다.

### A. 기본 방식 (No Namespace)
```bash
ros2 launch turtlebot3_bringup robot.launch.py
```

### B. 네임스페이스 방식 (TB3_2)
로봇 내부 노드들도 네임스페이스를 가지도록 실행합니다.
```bash
ros2 launch turtlebot3_bringup robot.launch.py __ns:=/TB3_2
```

## 3. SLAM 노드 실행
PC(Remote PC)에서 실행합니다.

### A. SLAM Toolbox 방식 (추천)
Cartographer보다 설정이 간편하고 지도가 더 정밀하게 생성되는 경향이 있습니다.
```bash
ros2 launch slam_toolbox online_async_launch.py use_sim_time:=false
```

### B. Cartographer 방식 (TB3_2 네임스페이스)
네임스페이스(`TB3_2`) 환경에서 작업 시 사용합니다.
```bash
ros2 launch patrol_main tb3_2_cartographer.launch.py
```
* **주의**: 이 방식은 RViz에서 `Fixed Frame`을 **`TB3_2/map`**으로, `Map`의 `Durability Policy`를 **`Transient Local`**로 설정해야 지도가 나타납니다.

## 4. 수동 조작 (Teleop)
로봇을 움직여 맵을 그립니다.
```bash
# 기본 조작
ros2 run turtlebot3_teleop teleop_keyboard

# 네임스페이스/속도 조절 필요 시
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r cmd_vel:=/cmd_vel -p repeat_rate:=10.0
```

## 5. 맵 저장
```bash
# maps 폴더에서 실행 (파일명: map_final)
ros2 run nav2_map_server map_saver_cli -f ~/map_final
```
* 저장 후 `map_final.yaml`과 `map_final.pgm` 파일이 생성되었는지 확인하세요.

## 6. 빌드 및 설정 (패키지)

### A. 빌드 및 실행
```bash
# 워크스페이스 루트에서 실행
colcon build --packages-select patrol_main
source install/setup.bash
ros2 launch patrol_main patrol.launch.py
```

### B. 진열대 좌표 설정 (YAML)
`src/patrol_main/config/shelf_coords.yaml` 파일은 반드시 다음과 같은 **중첩 구조(ros__parameters)**를 가져야 합니다.
```yaml
/**:
  ros__parameters:
    shelves:
      shelf_1: {x: 0.5, y: 0.0, yaw: 0.0}
```

## 7. 순찰 스케줄링 모드 설정 (Dynamic Parameter)
순찰 스케줄러는 두 가지 모드를 지원하며, 실시간으로 파라미터를 변경하여 적용할 수 있습니다.

### 모드 1: 기준 시점 기반 주기 순찰 (Periodic)
... (생략) ...
# (기존 내용 유지)

### 모드 3: 수동 순찰 실행 (Manual Trigger)
스케줄과 상관없이 UI 또는 터미널에서 즉시 순찰을 시작합니다.
- 서비스명: `/trigger_manual_patrol`
- 서비스 타입: `std_srvs/srv/Trigger`

```bash
# 터미널에서 즉시 순찰 시작 명령
ros2 service call /trigger_manual_patrol std_srvs/srv/Trigger {}
```

## 8. 문제 해결 (Troubleshooting)

### A. `tf2` 프레임 에러 (`/base_scan` 관련)
ROS 2 Humble 이상에서는 프레임 ID 처음에 슬래시(`/`)가 있으면 오류가 발생합니다.
- **증상**: `slam_toolbox`에서 `Invalid argument "/base_scan"` 에러 발생
- **해결**: 로봇의 `robot.launch.py`에서 `frame_id` 설정 시 슬래시를 제거했습니다. (`base_scan`으로 사용)

### B. 시간 동기화 에러 (`TF_OLD_DATA` 관련)
로봇과 PC의 시간이 맞지 않으면 데이터가 무시됩니다.
- **증상**: `Warning: TF_OLD_DATA` 또는 `Message Filter dropping message`
- **해결**: 
  1. 로봇에서 자동 시간 동기화 일시 중지: `sudo systemctl stop systemd-timesyncd`
  2. PC 시간으로 로봇 시간 설정: `ssh penguin@192.168.1.201 "sudo date -s @$(date +%s)"` (PC 터미널에서 실행)

### C. 노드 크래시 (Import Error)
- **증상**: `NameError: name 'time' is not defined`
- **해결**: `patrol_node.py` 상단에 `import time`이 누락되었던 문제를 수정하였습니다.
