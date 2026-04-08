# 순찰 시스템 제어 및 API 가이드 (Patrol & API Guide)

이 문서는 Gilbot의 **순찰 스케줄러**, **장애물 회피 연동**, 그리고 **Python API(`PatrolInterface`)** 사용법을 설명합니다.

---

## 1. 순찰 시스템 실행
순찰 노드와 장애물 회피 패키지가 포함된 통합 로직을 실행합니다 (PC).
```bash
cd ~/Documents/GitHub/AI_Robot_Final_Project202603/logic01
colcon build --packages-select patrol_main protect_product_msgs protect_product
source install/setup.bash
ros2 launch patrol_main patrol.launch.py
```

---

## 2. 장애물 회피 및 대기 시간 설정
- **장애물 노드(`obstacle_node`)**: `patrol_main` 패키지로 통합되었습니다. `twist_mux` 연동으로 장애물 감지 시 안전 거리를 유지하며 정지합니다.
- **연동 파라미터**: `current_wait_time` (초). 정지 후 대기 시간이 지나면 우회 시퀀스가 작동합니다.
- **설정 변경**: UI에서 '장애물 인식 조절' 슬라이더를 통해 실시간으로 변경 가능합니다.

---

## 3. 웹 서버 동기화 (Hybrid Sync Strategy)
네트워크 효율성과 실시간성을 위해 하이브리드 동기화 방식을 채용했습니다.

- **즉시 동기화 (Immediate Sync)**: 노드 실행과 동시에 **8000번 포트**를 통해 서버 최신 설정을 즉각 가져와 로봇에 반영합니다. (기존 15초 대기 불필요)
- **실시간 갱신 (Event-driven)**: UI에서 설정을 바꾸고 [확인]을 누르면, 로봇이 즉시 **`RECONFIG`** 신호를 받아 서버 데이터를 새로 읽어들입니다.
- **순찰 도중 (On-Demand)**: 순찰 시작 직전에 항상 최신 순찰 계획과 설정을 동기화하여 실시간성을 보장합니다.

---

## 4. 순찰 상태 리포트 (Real-time Status)
순찰 중에는 `/patrol_status` 토픽을 통해 실시간 JSON 정보를 발행합니다.

- **모니터링**: `ros2 topic echo /patrol_status`
- **주요 정보**: 현 위치(x, y), 현재 목표 선반, 진행률, 바코드 인식 결과 포함.
- **미니맵 연동**: `/patrol/list` API를 통해 서버에 기록된 최신 좌표가 UI 미니맵에 시각화됩니다.

---

### 5. 파이썬 API 사용 가이드 (PatrolInterface)
UI 파트에서 복잡한 ROS 2 명령어 없이 파이썬 함수 호출만으로 시스템을 제어할 수 있도록 `PatrolInterface` 클래스를 제공합니다.

- **안정성 개선**: `last_command_execution_times` 및 `processed_ids` 초기화 로직이 강화되어, 원격 명령 폴링 시 발생하던 `AttributeError`가 해결되었습니다.
- **상태 관리**: 명령 실행 이력이 내부적으로 안전하게 관리되어 중복 실행을 방지합니다.

```python
from patrol_main.patrol_interface import PatrolInterface

# 인터페이스 초기화 (Port 8000 직접 연결)
patrol = PatrolInterface()

# 1. 원격 설정과 실시간 동기화
# UI에서 값이 바뀌면 자동으로 로봇 노드에 RECONFIG 신호를 보냅니다.

# 2. 수동 순찰 즉시 실행
patrol.trigger_manual_patrol()

# 3. 최근 순찰 정보 및 서버 좌표 가져오기
status = patrol.get_recent_patrol_time()
print(f"현재 봇 위치: {status.get('robot_x')}, {status.get('robot_y')}")

# 작업 완료 후 종료 (필수)
patrol.shutdown()
```

---

## 6. 특징 및 권장 설정
- **강력한 경로 치환 (Python Pre-processing)**: `total_patrol.launch.py`는 이제 `RewrittenYaml`에만 의존하지 않고, Python의 `yaml` 라이브러리를 사용해 실행 시점에 경로를 직접 치환합니다. 이를 통해 어떤 환경에서도 `bt_navigator` 등의 경로 오류 없이 즉시 가동 가능합니다.
- **네임스페이스 지원**: 모든 서비스 경로를 절대 경로(예: `/obstacle_node/set_parameters`)로 사용하여 확장성을 높였습니다.
- **장애 대응**: 서버 연결이 일시적으로 끊겨도 로봇은 **가장 최근에 성공적으로 가져온 설정**을 유지하여 작동합니다.

---

 더 강력한 내비게이션 설정은 `config/nav2_params.yaml`을 참고하세요.
