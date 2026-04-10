# 순찰 시스템 제어 및 API 가이드 (Patrol & API Guide)

이 문서는 Gilbot의 **순찰 스케줄러**, **장애물 회피 연동**, 그리고 **Python API(`PatrolInterface`)** 사용법을 설명합니다.

---

## 1. 순찰 시스템 실행
순찰 노드와 장애물 회피 패키지가 포함된 통합 로직을 실행합니다 (PC).
```bash
cd ~/Documents/GitHub/AI_Robot_Final_Project202603/logic01
colcon build --packages-select patrol_main protect_product_msgs protect_product
source install/setup.bash
ros2 launch patrol_main total_patrol.launch.py
```

> [!TIP]
> 이제 **`total_patrol.launch.py`** 하나로 내비게이션, 장애물 회피, 그리고 [통합 AI 인식 시스템](./README_AI_VISION.md)이 한꺼번에 가동됩니다.

---

## 2. 주요 업데이트 사항 (v0.0.18+)

- **방향(Yaw) 동기화**: 서버 DB의 `loc_yaw` 컬럼과 연동되어, 로봇이 각 매대 지점에 도착했을 때 정확한 방향을 바라보도록 동기화되었습니다.
- **AI 인식 세이프가드 (10s Failsafe)**: 네트워크 지연이나 인식 프로세스 정지로 인해 로봇이 멈추는 현상을 방지하기 위해, 최대 10초 대기 후 자동으로 다음 목표로 주행하는 안전장치가 추가되었습니다.
- **내비게이션 회복력 강화**: 주행 중 장애물 등으로 인해 `ABORTED`(Status 5) 또는 `CANCELED`(Status 6)가 발생해도 순찰이 즉시 종료되지 않고, 3초 대기 후 재시도하거나 상태를 유지하도록 개선되었습니다.
- **배터리 모니터링 정밀화**: 로봇의 배터리 전압 상태(0.0~1.0 및 0~100 범위 모두 대응)를 자동으로 퍼센트 단위로 변환하여 서버에 정확히 보고합니다.
- **API 서버 연결 표준화**: 모든 통신 엔드포인트에서 `/api` 접두사를 제거하고 포트 8000의 루트 경로를 사용하도록 통일되었습니다.

---

## 3. 웹 서버 동기화 (Hybrid Sync Strategy)
네트워크 효율성과 실시간성을 위해 하이브리드 동기화 방식을 채용했습니다.

- **즉시 동기화 (Immediate Sync)**: 노드 실행과 동시에 서버 최신 설정(`avoidance_wait_time`, `ai_wait_timeout`)을 즉각 가져와 로봇에 반영합니다.
- **온디맨드 연산 (Power Saving)**: 인식 대기 중일 때만 YOLO 및 QR 분석 엔진이 구동되어 평시 전력 소모를 최소화합니다.
- **AI 인식 고도화 (Polling)**: 선반 도착 후 단발성 인식에 의존하지 않고, 서버 설정값(기본 8~10초) 동안 최신 데이터를 폴링하여 가장 정확한 판독 결과를 기록합니다.
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
- **실시간 장애물 대응**: `ObstacleNode`를 통해 전방 및 후방 장애물을 실시간 감지하며, AI 인식 모드와 연동되어 인식 시 감지 로직을 일시 정지(Pause)합니다.
- **강력한 경로 치환 (Python Pre-processing)**: `total_patrol.launch.py`는 실행 시점에 경로를 직접 치환하여 어떤 환경에서도 즉시 가동 가능합니다.
- **안전을 위한 초기 위치 보정 제거**: 주행 안정성을 위해 노드 시작 시 (0,0,0)으로 강제 리셋하던 로직을 제거했습니다. 이제 UI의 `initialpose` 기능을 활용하거나 AMCL의 마지막 저장 위치를 사용하십시오.
- **카메라 지연 최적화 (TCP mode)**: [AI 비전 가이드](./README_AI_VISION.md)에 따라 TCP 송출을 사용하여 대역폭 저하 상황에서도 끊김 없는 영상을 보장합니다.
- **장애 대응**: 서버 연결이 일시적으로 끊겨도 로봇은 **가장 최근에 성공적으로 가져온 설정**을 유지하여 작동합니다.

---

 더 강력한 내비게이션 설정은 `config/nav2_params.yaml`을 참고하세요.
