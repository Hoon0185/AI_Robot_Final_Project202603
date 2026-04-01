# 순찰 로봇 시스템 작동 확인 가이드 (Patrol Operation Guide)

이 문서는 순찰 로봇의 안정적인 가동을 위해 권장되는 **단계별 분리 실행** 절차를 설명합니다. 일괄 실행(`total_patrol.launch.py`) 시 하드웨어 자원이나 네트워크 문제로 오류가 발생할 경우, 아래의 순서대로 진행해 주십시오.

---

## 1. 사전 준비 사항
*   **ROS 2 Humble** 및 필수 의존성 설치
*   **FastAPI 백엔드** 서버 가동 (`http://16.184.56.119`)
*   **터틀봇3 하드웨어** 및 PC 간의 시간 동기화 완료 (`chrony`)

---

## 2. 단계별 실행 절차 (권장: 분리 실행)

가장 안정적인 방법은 내비게이션, 순찰 로직, AI 인식, 로봇 센서를 별도의 터미널에서 순차적으로 실행하는 것입니다.

### [Step 0] 내비게이션 및 맵 실행 (PC)
내비게이션 스택을 먼저 실행하여 맵과 위치 추정(AMCL)을 활성화합니다.
```bash
# 터미널 1
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
  use_sim_time:=false \
  autostart:=true \
  map:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/maps/my_store_map_01.yaml \
  params_file:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/src/patrol_main/config/nav2_params.yaml \
  cmd_vel:=cmd_vel_nav
```

### [Step 1] 순찰 시스템 실행 (PC)
순찰 스케줄러, 메인 노드, 장애물 회피, 멀티플렉서를 실행합니다.
```bash
# 터미널 2 (PC)
source install/setup.bash
ros2 launch patrol_main patrol.launch.py
```

### [Step 2] AI 인식 시스템 실행 (PC)
물품 탐지 및 바코드 검증 노드를 실행합니다.
```bash
# 터미널 3 (PC)
source install/setup.bash
# [실제 카메라 사용 시]
ros2 launch protect_product ai_detection.launch.py
# [카메라 없이 테스트 시] 
ros2 launch protect_product ai_detection.launch.py use_ai_sim:=true
```
*(참고: `ai_detection.launch.py`가 없는 경우 `detector_node`와 `verifier_node`를 각각 실행하십시오.)*

### [Step 3] RFID 센서 노드 실행 (Robot - SSH)
로봇 본체(Raspberry Pi)에 직접 접속하여 RFID 리딩 및 위치 보정 노드를 실행합니다.
```bash
# 터미널 4 (PC에서 SSH 접속)
ssh penguin@192.168.0.8

# 로봇 접속 후 실행 (홈 디렉토리의 rfid 폴더)
cd ~/rfid
python3 rfid_robot_node.py
```

### [Step 4] 관리용 UI 실행 (PC)
최종 제어 UI를 실행하여 시스템을 모니터링합니다.
```bash
# 터미널 5 (PC)
python3 main.py
```

---

## 3. 통합 실행 (Total Launch - 간편 모드)
시스템 자원이 충분하고 네트워크가 안정적인 경우, 아래 명령어로 한 번에 실행할 수 있습니다.
```bash
ros2 launch patrol_main total_patrol.launch.py use_ai_sim:=false
```

---

## 4. 기능 확인 및 트러블슈팅
*   **RFID 작동**: 로봇이 태그 근처를 지날 때 터미널 4에서 `Landmark Corrected!` 로그가 발생하는지 확인합니다.
*   **AI 리포팅**: `/verif_img/compressed` 토픽을 통해 인식 결과를 확인합니다.
*   **통신 오류**: 각 터미널의 로그를 확인하여 `Connection refused` 또는 `Timeout` 메시지가 있는지 점검하십시오.
*   **리매핑**: 개별 실행 시 Nav2의 `cmd_vel`이 `/cmd_vel_nav`로 리매핑되어 `twist_mux`를 통과하는지 반드시 확인해야 합니다.
