# 순찰 시스템 제어 및 API 가이드 (Patrol & API Guide)

이 문서는 Gilbot의 **순찰 스케줄링**, **실시간 상태 모니터링**, 그리고 **Python API(`PatrolInterface`)** 사용법을 설명합니다.

---

## 1. 순찰 시스템 실행
순찰 로직을 활성화하려면 다음 명령어를 실행합니다 (PC).
```bash
cd ~/Documents/GitHub/AI_Robot_Final_Project202603/logic01
colcon build --packages-select patrol_main
source install/setup.bash
ros2 launch patrol_main patrol.launch.py
```

---

## 2. 순찰 스케줄링 및 모드 설정 (CLI vs Python API)
순찰 스케줄러는 실시간으로 파라미터를 변경하여 즉시 적용할 수 있습니다.

### 모드 1: 주기 순찰 (Periodic)
특정 기준 시점부터 일정한 간격(분 단위)으로 순찰을 반복합니다.
- **터미널 (CLI)**:
    ```bash
    ros2 param set /patrol_scheduler patrol_mode "periodic"
    ros2 param set /patrol_scheduler patrol_interval_min 60.0
    ros2 param set /patrol_scheduler reference_time "00:00"
    ```
- **파이썬 (API)**:
    ```python
    patrol.set_patrol_mode("periodic")
    patrol.set_patrol_interval(60.0)
    ```

### 모드 2: 특정 시각 목록 순찰 (Scheduled)
미리 정의된 시간 목록에 무조건 순찰을 시작합니다.
- **터미널 (CLI)**:
    ```bash
    ros2 param set /patrol_scheduler patrol_mode "scheduled"
    ros2 param set /patrol_scheduler scheduled_times ["09:00", "13:00", "18:00"]
    ```

### 모드 3: 수동 순찰 실행 (Manual Trigger)
스케줄과 상관없이 즉시 순찰을 시작합니다.
- **터미널 (CLI)**:
    ```bash
    ros2 service call /trigger_manual_patrol std_srvs/srv/Trigger {}
    ```

---

## 3. 웹 서버 동기화 (Database Sync)
 Gilbot은 PC의 DB와 연동하여 실시간으로 설정값을 동기화합니다.
- **자동 업데이트**: 웹 관리자 페이지에서 순찰 간격이나 모드를 변경하면, `patrol_scheduler`가 자동으로 감지하여 ROS 파라미터를 업데이트합니다.
- **연결 확인**: UI 상단의 `Robot Online` 표시등이 초록색인지 확인하세요.

---

## 4. 순찰 상태 리포트 (Real-time Status)
순찰 중에는 `/patrol_status` 토픽을 통해 실시간 JSON 정보를 발행합니다.

- **모니터링**: `ros2 topic echo /patrol_status`
- **주요 정보**: 현 위치(x, y), 현재 목표 선반, 진행률, 바코드 인식 결과 포함.

---

## 5. 파이썬 API 사용 가이드 (PatrolInterface)
UI 파트에서 복잡한 ROS 2 명령어 없이 파이썬 함수 호출만으로 시스템을 제어할 수 있도록 `PatrolInterface` 클래스를 제공합니다.

```python
from patrol_main.patrol_interface import PatrolInterface

# 인터페이스 초기화
patrol = PatrolInterface()

# 1. 순찰 모드 설정
patrol.set_patrol_mode("periodic")

# 2. 순찰 간격 설정 (분 단위, 예: 30분)
patrol.set_patrol_interval(30.0)

# 3. 수동 순찰 즉시 실행
patrol.trigger_manual_patrol()

# 4. 최근 순찰 정보 가져오기
status = patrol.get_recent_patrol_time()
print(f"현재 상태: {status}")

# 작업 완료 후 종료 (필수)
patrol.shutdown()
```

---

## 6. 특징 및 권장 설정
- **비차단형 지연(Non-blocking Delay)**: 선반 도착 후 인식 시 `timer`를 사용하여 노드 통신을 유지합니다.
- **장애 대응(Fault Tolerance)**: 경로 차단 시 자동으로 해당 지점을 건너뛰고 다음 목표로 진행합니다.

---

 더 강력한 장애물 회피 및 멀티플렉싱 설정은 `config/nav2_params.yaml`을 참고하세요.
