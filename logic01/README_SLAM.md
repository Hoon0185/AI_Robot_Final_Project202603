# SLAM 및 맵 생성 가이드 (Member A용)

사용자(팀원 A)가 담당하는 SLAM 및 맵 생성을 위한 절차입니다. 터틀봇3 기준 명령어입니다.

## 1. 터틀봇3 기기 연결 및 환경 변수 설정
터틀봇과 PC에서 모두 설정되어 있어야 합니다.
```bash
export TURTLEBOT3_MODEL=burger  # 또는 waffle_pi
```

## 2. SLAM 노드 실행
PC(Remote PC)에서 실행합니다.
```bash
ros2 launch turtlebot3_cartographer cartographer.launch.py
```

## 3. 수동 조작 (Teleop)
다른 터미널에서 로봇을 움직여 맵을 그립니다.
```bash
ros2 run turtlebot3_teleop teleop_keyboard
```
* 맵을 그릴 때 너무 빨리 움직이지 않도록 주의하세요. 특히 회전할 때 천천히 해야 맵이 뒤틀리지 않습니다.

## 4. 맵 저장
맵이 완성되면 워크스페이스 내의 `maps` 폴더에 저장합니다. (현재 위치: `logic01/maps`)
```bash
# logic01 폴더로 이동 후 실행하거나 적절한 상대 경로를 지정하세요.
cd logic01/maps
ros2 run nav2_map_server map_saver_cli -f map
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

## 6. 순찰 주기 변경 (Dynamic Parameter)
실시간으로 순찰 주기를 변경하려면 다른 터미널에서 다음 명령어를 실행하세요:
```bash
# 주기를 30초로 변경 예시
ros2 param set /patrol_scheduler patrol_interval 30.0
```
이후 UI(웹 서버 등)가 완성되면 이 파라미터를 조작하여 주기를 관리할 수 있습니다.
