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

- **방향(Yaw) 동기화**: 서버 DB의 `loc_yaw` 컬럼과 연동되어, 로봇이 각 매대 지점에 도착했을 때 정확한 방향(예: B구역 180도)을 바라보도록 동기화되었습니다.
- **AI 인식 모드 동기화**: `patrol_node`와 `obstacle_node`가 **`/ai_mode_active`** 토픽을 통해 연동됩니다. AI 인식 지점 도착 시 장애물 감지 기능을 일시 정지하여 로봇 구성물(팔, 선반 등)에 의한 오작동을 방지합니다.
- **설정 변경**: 웹 대시보드 관리자 페이지에서 설정을 변경하면 로봇이 즉시 `RECONFIG` 신호를 받아 반영합니다.
- **주행 복구 능력 (Advanced Integration)**: 주행 중 예기치 않은 오류(`ABORTED`) 발생 시, 2초 후 자동으로 현재 목표를 재전송하는 타이머가 도입되어 주행 연속성이 대폭 강화되었습니다.
- **DB 접속 표준화**: 모든 노드는 하드코딩된 주소 대신 `InventoryDB` 패키지의 표준 설정(`16.184.56.119:8000`)을 공유하여 관리 포인트가 일원화되었습니다.

---

## 3. 웹 서버 동기화 (Hybrid Sync Strategy)
네트워크 효율성과 실시간성을 위해 하이브리드 동기화 방식을 채용했습니다.

- **즉시 동기화 (Immediate Sync)**: 노드 실행과 동시에 서버 최신 설정(`avoidance_wait_time`, `ai_wait_timeout`)을 즉각 가져와 로봇에 반영합니다.
- **AI 인식 고도화 (8s Polling)**: 선반 도착 후 단발성 인식에 의존하지 않고, **최대 8초간** 최신 데이터를 폴링하여 가장 정확한 판독 결과를 기록합니다.
- **실시간 갱신 (Event-driven)**: 웹 대시보드에서 설정을 바꾸면, 로봇이 즉시 **`RECONFIG`** 신호를 받아 서버 데이터를 새로 읽어들입니다.
- **순찰 도중 (On-Demand)**: 순찰 시작 직전에 항상 최신 순찰 계획과 좌표(`TAG-A1-001` 등)를 DB에서 동기화하며, 동시에 로컬 `shelf_coords.yaml`을 최신 상태로 갱신하여 데이터 일관성을 유지합니다.

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
- **주행 연속성 보장**: 이전에는 주행 중 취소(`CANCELED`)나 중단(`ABORTED`) 발생 시 순찰이 종료되었으나, 현재는 **자동 재시도 타이머**를 통해 상태를 유지하며 자동으로 다시 출발합니다.
- **자동 초기 위치 보정 (Auto Sync)**: 노드 시작 1초 후 자동으로 `(0,0,0)` 위치로 `initialpose`를 발행하여, 사용자의 수동 조작 없이도 AMCL이 즉시 가동되도록 개선되었습니다.
- **카메라 지연 최적화 (Lag-Free Stream)**: `camera_node`에서 누적된 버퍼를 강제로 비우는 로직을 도입하여, RTSP 영상의 고질적인 수 초 지연 현상을 완전히 해결했습니다.
- **장애 대응**: 서버 연결이 일시적으로 끊겨도 로봇은 **가장 최근에 성공적으로 가져온 설정**을 유지하여 작동합니다.

---

 더 강력한 내비게이션 설정은 `config/nav2_params.yaml`을 참고하세요.
