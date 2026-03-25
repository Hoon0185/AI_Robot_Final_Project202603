## 🚀 기능 개요

💡 **기능명 : SLAM 및 맵핑**
목적 : SLAM Toolbox를 활용한 정밀 맵 생성 및 Lidar frame_id 최적화를 통한 데이터 정합성 확보.

💡 **기능명 : 순찰 스케줄러**
목적 : 정해진 시간(주기/목록) 순찰뿐만 아니라, 필요 시 즉시 순찰을 시작할 수 있는 전용 서비스(Manual Trigger) 인터페이스 제공.

💡 **기능명 : 웨이포인트 내비게이션 및 시각화**
목록 : ROS2 표준 파라미터 구조를 따르는 YAML 설정 파일을 통해 진열대 좌표를 유연하게 관리하며, RViz 상에서 실시간으로 마커(MarkerArray)를 가시화하여 직관적인 순찰 경로 확인 가능.

---

## 📋 기능 명세 및 요구사항

💡 **사용자 시나리오 :**
사용자는 로봇을 편의점 환경에 배치하고 순찰 시스템을 가동한다. 로봇은 설정된 주기(기본 60초)마다 자동으로 순찰을 시작하여 지정된 모든 진열대를 순차적으로 방문한다. 필요 시 사용자는 UI(또는 CLI)를 통해 순찰 주기를 실시간으로 변경할 수 있다.

---

## 🛠️ 기술적 세부사항

💡 **핵심 로직:**
1. **복합 순찰 스케줄러**: `periodic`, `scheduled` 모드와 더불어 `Trigger` 서비스를 통한 **수동 모드** 지원.
2. **YAML 파라미터 동적 바인딩**: ROS2의 `/**: ros__parameters` 구조를 채택하여 안정적인 좌표 로드 및 실시간 파라미터 업데이트 반영.
3. **SLAM 및 시각화 최적화**: SLAM Toolbox 전환 및 Lidar `frame_id` 정합성 해결. 특히 `patrol_visualizer`를 통해 설정된 좌표를 지점(Sphere)과 이름(Text)으로 RViz에 실시간 투영.
4. **Action 기반 정밀 내비게이션**: Nav2 액션 서버의 결과 상태(`GoalStatus.STATUS_SUCCEEDED`)를 엄격히 검증하여 정확한 도착 여부를 판단 후 다음 지점으로 이동.

### **1. Patrol Scheduler (복합 모드 지원)**

```python
def __init__(self):
    super().__init__('patrol_scheduler')
    # 1. 파라미터 선언 (분 단위)
    self.declare_parameter('patrol_interval_min', 60.0)
    self.update_interval() # 분 -> 초 계산 함수 호출
    
    # 2. 정각을 체크하기 위해 1초마다 시계를 확인하는 타이머 생성
    self.timer = self.create_timer(1.0, self.clock_check_callback)
    self.add_on_set_parameters_callback(self.parameter_callback)
    self.last_triggered_time = -1

def parameter_callback(self, params):
    for param in params:
        if param.name == 'patrol_interval_min': # 파라미터 이름 일치 확인
            self.interval_min = param.value
            self.interval_sec = self.interval_min * 60.0 # 초 단위 업데이트
            return SetParametersResult(successful=True)
    return SetParametersResult(successful=True)
    
# 핵심 logic: 모드에 따른 트리거 조건 분기
def clock_check_callback(self):
    now = time.localtime()
    current_timestamp = int(time.time())
    # 자정 이후 경과된 초 계산
    seconds_since_midnight = now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec
    if self.mode == 'periodic':
        # 기준 시점(ref_offset_sec)으로부터 주기(interval_sec)가 정확히 경과했는지 계산
        diff = seconds_since_midnight - self.ref_offset_sec
        if diff >= 0 and diff % int(self.interval_sec) == 0:
            if current_timestamp != self.last_triggered_time:
                self.trigger_patrol("Periodic Mode")
                self.last_triggered_time = current_timestamp
```

### **2. Patrol Main Node (순차 방문 로직)**

```python
def send_next_goal(self):
    if self.current_shelf_idx >= len(self.shelf_list):
        self.is_patrolling = False
        return

    shelf_name = self.shelf_list[self.current_shelf_idx]
    coords = self.shelves[shelf_name]
    
    goal_msg = NavigateToPose.Goal()
    goal_msg.pose.pose.position.x = float(coords['x'])
    goal_msg.pose.pose.position.y = float(coords['y'])
    # ... orientation 설정 생략 ...
    self._action_client.send_goal_async(goal_msg)
```

### **3. Manual Trigger Service Interface**

```python
# scheduler 노드에 추가된 수동 시작 인터페이스
def __init__(self):
    # ...
    self.srv = self.create_service(Trigger, 'trigger_manual_patrol', self.manual_trigger_callback)

def manual_trigger_callback(self, request, response):
    self.trigger_patrol("Manual Service Call")
    response.success = True
    response.message = "Patrol started manually."
    return response
```

### **4. ROS2 표준 YAML 구조 반영**

```yaml
/**:
  ros__parameters:
    shelves:
      shelf_1: {x: 0.5, y: 0.0, yaw: 0.0}
      # ... (중합 구조를 통한 표준 파라미터 호환성 확보)
```

---

## 📸 스크린샷 or 영상

💡 **매핑 및 내비게이션 실행 화면**
* [이곳에 RViz 실행화면이나 로봇 주행 영상을 업로드하세요]

---

## 📈 이슈 및 특이사항 (최종 업데이트)

💡 **문제점 리포트:**
1. **문제점 01**: 초기 구현 시 순찰 주기를 변경해도 즉시 반영되지 않고 다음 주기부터 반영되는 문제 발생.
2. **문제점 02**: Nav2 액션 서버가 준비되지 않은 상태에서 호출 시 노드가 대기 상태에 빠질 우려가 있음.
3. **문제점 03**: 동일 망, 동일 도메인을 사용하는 다른 터틀봇과 구분하기 위해 네임스페이스(`TB3_2`) 환경에서 기본 SLAM 런칭 파일 사용 시, TF 프레임 이름(`map`, `odom` 등)이 하드코딩되어 있어 로봇 센서 데이터와 맵 데이터가 연결되지 않는 현상 발생.
4. **문제점 04**: RViz에서 맵 토픽은 정상적이나 "No map received" 에러와 함께 지도가 가시화되지 않는 문제.
5. **문제점 05**: 연결이 다소 불안정하고 맵 해상도가 낮음.
6. **문제점 06**: 터틀봇과 원격 PC의 시간차로 인해 데이터 수신에 실패.
7. **문제점 07 (YAML 파싱 에러)**: 일반 딕셔너리 형태의 YAML 로드 시 ROS 2 파라미터 서버와의 불일치로 `KeyError: 'shelves'` 발생.
8. **문제점 08 (Frame Identifier 에러)**: Lidar 데이터의 `frame_id`가 `/base_scan`으로 선행 슬래시가 포함되어 있어 ROS 2 Humble의 TF2와 호환되지 않음.
9. **문제점 09 (Node Crash)**: `patrol_node` 내에서 `time.sleep()` 사용 시 모듈 `import time`이 누락되어 런타임 에러 발생.
10. **문제점 10 (TF Latency)**: 로봇과 PC 간의 미세한 시간 차이로 인해 SLAM에서 로봇 위치가 표시되지 않거나 `TF_OLD_DATA` 에러 지속 발생.
11. **문제점 11 (Logical Bug)**: 내비게이션 결과가 실패(장애물 등)해도 무조건 "도착"으로 간주하고 다음 목표로 진행하는 현상.

💡 **해결 방안:**
1. **해결 01**: 물리적 타이머의 재시작 오차를 방지하기 위해 **1Hz 주기의 '시계 감시(Clock Watchdog)' 로직**을 도입함.
... (중략) ...
9. **해결 09**: 전역 스코프에 `import time` 추가 및 타이머 콜백 내에서의 안정적인 딜레이 처리 로직 구현.
10. **해결 10**: `systemd-timesyncd` 비활성화 후 PC 시각 기반 정밀 수동 동기화(`date -s`) 명령을 가이드하여 TF 정합성 100% 확보.
11. **해결 11**: `get_result_callback`에서 `GoalStatus`를 필터링하여 오직 **SUCCESS** 상태일 때만 도착으로 기록하도록 로직 강화.
