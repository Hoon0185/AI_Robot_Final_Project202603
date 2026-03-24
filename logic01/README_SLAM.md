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
PC(Remote PC)에서 실행합니다. 로봇 환경(네임스페이스 사용 여부)에 따라 선택하세요.

### A. 기본 방식 (Single Robot / No Namespace)
가장 표준적인 방법입니다.
```bash
ros2 launch turtlebot3_cartographer cartographer.launch.py
```

### B. 네임스페이스 방식 (Multi Robot / `TB3_2` 전용)
여러 대의 로봇을 운용하거나 특정 이름표가 붙은 경우 사용합니다.
```bash
ros2 launch patrol_main tb3_2_cartographer.launch.py
```
* **주의**: 이 방식은 RViz에서 `Fixed Frame`을 **`TB3_2/map`**으로, `Map`의 `Durability Policy`를 **`Transient Local`**로 설정해야 지도가 나타납니다.

## 3. 수동 조작 (Teleop)
로봇을 움직여 맵을 그립니다.
```bash
# A. 기본 방식
ros2 run turtlebot3_teleop teleop_keyboard

# B. 네임스페이스 방식 (부드러운 주행 옵션 포함)
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r cmd_vel:=/TB3_2/cmd_vel -p repeat_rate:=10.0
```

## 4. 맵 저장
```bash
# A. 기본 방식 (maps 폴더에서 실행)
ros2 run nav2_map_server map_saver_cli -f map

# B. 네임스페이스 방식 (maps 폴더에서 실행)
ros2 run nav2_map_server map_saver_cli -f my_map --ros-args -r map:=/TB3_2/map
```
* 저장 후 `map.yaml`과 `map.pgm` 파일이 생성되었는지 확인하세요.

## 5. 빌드 및 실행 (패키지)
작업한 소스코드를 빌드하려면:
```bash
# logic01 폴더(워크스페이스 루트)에서 실행
cd logic01
colcon build --symlink-install
source install/setup.bash
ros2 launch patrol_main patrol.launch.py
```

## 6. 순찰 스케줄링 모드 설정 (Dynamic Parameter)
순찰 스케줄러는 두 가지 모드를 지원하며, 실시간으로 파라미터를 변경하여 적용할 수 있습니다.

### 모드 1: 기준 시점 기반 주기 순찰 (Periodic)
특정 시각을 기준으로 일정 간격마다 순찰합니다.
- `patrol_mode`: `"periodic"` (기본값)
- `reference_time`: `"HH:MM"` (기준 시점, 기본 `"00:00"`)
- `patrol_interval_min`: `분단위` (주기, 기본 `60.0`)

```bash
# 예시: 09:10분부터 30분 간격으로 순찰 설정
ros2 param set /patrol_scheduler reference_time "09:10"
ros2 param set /patrol_scheduler patrol_interval_min 30.0
```

### 모드 2: 특정 시각 목록 순찰 (Scheduled)
지정된 시각들에만 순찰합니다.
- `patrol_mode`: `"scheduled"`
- `scheduled_times`: `["HH:MM", ...]` (시간 목록)

```bash
# 예시: 오전 9시, 오후 1시, 오후 6시에만 순찰하도록 설정
ros2 param set /patrol_scheduler patrol_mode "scheduled"
ros2 param set /patrol_scheduler scheduled_times '["09:00", "13:00", "18:00"]'
```
