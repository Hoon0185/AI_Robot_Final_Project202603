## 🚀 기능 개요

<aside>
💡 **기능명 : SLAM 및 맵핑**
목적 : SLAM Toolbox를 활용한 정밀 맵 생성 및 Lidar frame_id 최적화를 통한 데이터 정합성 확보.
</aside>

<aside>
💡 **기능명 : 순찰 스케줄러 및 명령 전파**
목적 : 주기(Periodic), 특정 시각(Scheduled) 순찰뿐만 아니라 전용 서비스(Manual Trigger) 및 절대 경로 토픽(`/patrol_cmd`)을 통해 시스템 전반에 순찰 명령을 동기화하는 복합 스케줄링 로직 구현.
</aside>

<aside>
💡 **기능명 : 웨이포인트 내비게이션 및 시각화**
목적 : ROS 2 표준 파라미터 구조(`YAML`)를 사용하여 진열대 좌표를 유연하게 관리하고, RViz 상에서 실시간으로 마커(MarkerArray)를 가시화하여 순찰 경로의 직관성 제공.
</aside>

---

## 📋 기능 명세 및 요구사항

<aside>
💡 **사용자 시나리오 :**
로봇이 편의점 환경에 배치되면, 시스템은 설정된 순찰 모드에 따라 자율 주행을 시작한다. 주기 모드에서는 정해진 시간 간격마다, 예약 모드에서는 지정된 특정 시각마다 순찰이 수행된다. 모든 진열대를 방문한 후 로봇은 다시 대기 상태로 돌아가며, 필요 시 UI를 통해 즉각적인 수동 순찰을 명령할 수 있다.
</aside>

---

## 🛠️ 기술적 세부사항

💡 **핵심 로직:**
3. **SLAM 및 TF 정합성 해결**: `systemd-timesyncd` 중단 후 수동 시간 동기화를 통해 TF 에러를 해결하고, `slam_toolbox`를 활용하여 실시간 지도 생성을 최적화함.
4. **지능형 장애물 회피 (LOGIC_02)**: `SetParameters` 서비스를 통해 Nav2의 `FollowPath.max_vel_x`를 제어하고 가상 벽을 활용하여 유연한 유도 기동 구현.

### **1. Patrol Scheduler (복합 모드 및 동적 업데이트)**

```python
def update_config(self, params=None):
    """파라미터 변경 시 내부 설정(간격, 모드 등)을 즉시 업데이트"""
    if params:
        for param in params:
            if param.name == 'patrol_interval_min':
                self.interval_sec = float(param.value) * 60.0
            elif param.name == 'patrol_mode':
                self.mode = param.value
            # ... 기타 파라미터 업데이트 ...
    else:
        # 초기화 시 현재 파라미터 값 로드
        self.mode = self.get_parameter('patrol_mode').value
        self.interval_sec = self.get_parameter('patrol_interval_min').value * 60.0

def parameter_callback(self, params):
    """동적 파라미터 업데이트 이벤트 핸들러"""
    self.get_logger().info('Updating parameters dynamically...')
    self.update_config(params)
    return SetParametersResult(successful=True)
```

### **2. Patrol Main Node (주행 제어 및 결과 처리)**

```python
def get_result_callback(self, future):
    """내비게이션 결과 수신 및 주행 중단 상황 방어 로직"""
    self._goal_handle = None
    status = future.result().status

    if status == GoalStatus.STATUS_SUCCEEDED:
        # 정상 도착 시 AI 검증 시퀀스 시작
        self.get_logger().info(f'[{shelf_name}] 도착 완료. AI 검증 대기 중...')
        self.start_ai_verification() 
    elif status == GoalStatus.STATUS_ABORTED or status == GoalStatus.STATUS_CANCELED:
        # 장애물 우회 등으로 인한 중단 시 순찰을 끄지 않고 유지
        self.get_logger().warn(f'Navigation interrupted (code: {status}). Maintaining patrol state.')
    else:
        # 복구 불가능한 에러 시에만 종료
        self.is_patrolling = False
        self.get_logger().error(f'Navigation failed. Stopping patrol.')
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
      TAG-A1-001: 
        tag_barcode: '8801043036436'
        waypoint_id: 2
        x: -0.5233, y: -0.2373, yaw: 0.0
      # ... (중합 구조를 통한 표준 파라미터 및 DB 메타데이터 통합 관리)
```

---

## 📸 스크린샷 및 영상

### **A. Namespace(TB3_2) + Cartographer SLAM**
![스크린샷 2026-03-24 15-02-30.png](attachment:e036ff28-8438-4ec6-ad5d-257bf17fd2be:스크린샷_2026-03-24_15-02-30.png)
![스크린샷 2026-03-24 15-03-20.png](attachment:77647712-d069-4c97-9815-53c68782a5f2:스크린샷_2026-03-24_15-03-20.png)
![스크린샷 2026-03-24 15-04-40.png](attachment:105fc5b8-363b-4a85-a660-bb5d61b1a66c:스크린샷_2026-03-24_15-04-40.png)
![스크린샷 2026-03-24 15-05-55.png](attachment:4a6ec7c9-f826-4508-8dcf-d437e6c71087:스크린샷_2026-03-24_15-05-55.png)

### **B. Namespace 미사용 + SLAM Toolbox**
![스크린샷 2026-03-25 10-49-29.png](attachment:ab7ececc-10d2-4d4a-afb4-88420810b371:스크린샷_2026-03-25_10-49-29.png)
![스크린샷 2026-03-25 10-52-26.png](attachment:d4444f10-94cb-400e-87b5-6256841ebc6d:스크린샷_2026-03-25_10-52-26.png)
![image.png](attachment:a1f5c2f1-dee8-4c92-806c-2757686eb670:image.png)
![image.png](attachment:abefe01e-2b57-4f71-8d81-b4b70086b171:image.png)

### **C. Nav2 내비게이션 주행**
![image.png](attachment:a7e171b7-7afe-4231-b0a9-81b381be5826:image.png)
![image.png](attachment:dc677549-385d-49e2-9a03-262154ea9c38:image.png)
![image.png](attachment:98f87bc5-4d32-4429-9237-ad903ccbf1c6:image.png)
![image.png](attachment:c564d00f-423e-4e86-b3d5-bdc29f180f19:image.png)

### **D. 실제 테스트 장소 및 핫스팟/장애물 환경**
![image.png](attachment:ce08cc74-bd0c-4b5e-9ee8-2c0cb0cbd9f9:image.png)
![image.png](attachment:53198a18-75ec-4892-a876-f9947cd6a198:image.png)
![image.png](attachment:6f64c708-8ea8-4e05-8efe-62b0ec4b24a0:image.png)
![image.png](attachment:a8199f60-adca-43f8-a1c4-6ff414addbaa:image.png)
![image.png](attachment:98813540-15a6-405c-94b9-b505d1fe9e67:image.png)
![6229.jpg](attachment:dbc04dcd-c10d-4ab2-ae26-e219fa11716f:6229.jpg)

### **E. 주행 테스트 영상**
- https://youtu.be/rt2OcQ-De8Y
- https://youtu.be/s2Q7INc73T0

---

## 📈 이슈 및 특이사항 (중복 정리본)

<aside>
💡 **1. 순찰 주기 변경 실시간 미반영:**
* 문제: 초기 구현 시 주기를 변경해도 즉시 반영되지 않고 다음 주기부터 적용됨.
* 해결: 1Hz 주기의 **시계 감시(Clock Watchdog)**로직을 도입하여 시스템 시각과 실시간 연동, 변경 즉시 다음 트리거 시점을 포착하도록 개선.

**14. 토픽 이름 충돌 및 절대 경로화:**
* 문제: `patrol_node`와 `scheduler`가 서로 다른 네임스페이스에 있을 때 명령 미수신 발생.
* 해결: `/patrol_cmd` 등 모든 제어 토픽을 **절대 경로**로 통일하여 해결.

**15. 세션 종료 누락 방지:**
* 문제: 순찰이 비정상 종료되거나 수동 중단될 때 서버 세션이 '진행 중'으로 남는 현상.
* 해결: `patrol_node`의 중단 로직 및 `PatrolInterface` 명령 시 `finish_patrol_session()`을 명시적으로 호출하도록 수정.

**16. 원격 명령 추적성 강화:**
* 문제: 서버에서 보낸 명령이 로봇에서 중복 실행되거나 실행 여부를 알 수 없음.
* 해결: `command_id` 기반의 **실행 체크 및 완료 보고(`complete_command`)** 로직을 API 스레드에 내장.

**3. 네임스페이스(TB3_2) 환경 정합성:**
* 문제: 프레임 이름(map, odom 등) 하드코딩으로 인한 데이터 단절 및 브로드캐스팅 누락.
* 해결: 전용 **LUA 설정 및 래퍼 런칭 파일** 작성, 명령어 실행 시 `__ns:=/TB3_2` 옵션 필수 적용.

**4. RViz "No map received" 시각화 이슈:**
* 문제: 맵 토픽은 정상이나 RViz에서 지도가 표시되지 않음.
* 해결: QoS 설정을 `Volatile`에서 `Transient Local`로 변경하여 지연 수신 데이터 처리.

**5. SLAM 방식 비교 및 최적화:**
* 문제: Cartographer 사용 시 연결 불안정 및 낮은 해상도 이슈.
* 해결: **SLAM Toolbox** 방식으로 전환하여 정밀도 및 실시간성 확보.

**6. 로봇-PC 간 시간 동기화(TF_OLD_DATA):**
* 문제: 미세한 시간 차이로 인한 TF 수신 실패 및 SLAM 위치 표시 오류.
* 해결: `systemd-timesyncd` 중지 후 PC 시각 기반 **강제 수동 동기화(`date -s`)** 가이드 적용.

**7. YAML 파싱 및 파라미터 서버 불일치:**
* 문제: 일반 YAML 로드 시 ROS 2 파라미터 서버와의 형식 불일치로 `KeyError` 발생.
* 해결: `/**: ros__parameters` 표준 구조 적용 및 내부 파싱 로직 강화.

**8. Lidar frame_id(/base_scan) 호환성 에러:**
* 문제: 선행 슬래시(/) 포함으로 인해 TF2와 호환되지 않는 현상.
* 해결: 런칭 파일 수정을 통해 `frame_id:=base_scan`으로 강제 할당하여 정합성 해결.

**9. 런타임 노드 크래시:**
* 문제: `time.sleep()` 사용 중 모듈 누락(`import time`) 및 차단형 대기로 인한 노드 멈춤.
* 해결: 전역 스코프 import 추가 및 ROS 2 타이머 기반의 **비차단형 딜레이** 로직 구현.

**10. 내비게이션 논리적 버그:**
* 문제: 장애물 등으로 인한 주행 실패 시에도 무조건 "도착"으로 간주하고 다음 목표 진행.
* 해결: `get_result_callback`에서 `GoalStatus.STATUS_SUCCEEDED` 상태값만 필터링하도록 로직 강화.

**11. 사용자 환경별 하드코딩 경로/IP 이슈:**
* 문제: 특정 IP 및 절대 경로 사용으로 인해 타 환경에서 명령어 실행 불가.
* 해결: IP 주소 예시 명시 및 `$HOME` 환경 변수를 활용한 가변 경로 대응.

**12. Humble 버전 플러그인 로딩 에러:**
* 문제: Nav2 파라미터 내 플러그인 구분자(`::`) 불일치로 인한 로딩 실패.
* 해결: 구분자를 전체적으로 `/`로 수정 (예: `nav2_behaviors/Spin`).

**13. 동적 업데이트 발생 시 성능 및 데드락:**
* 문제: 타이머 콜백 내에서 지속적인 `get_parameter` 호출로 인한 부하 및 데드락 위험.
* 해결: 전용 `update_config` 함수를 통한 **이벤트 기반(On Set Parameter)** 업데이트 로직 고도화.

**18. BT Navigator 경로 치환 실패 (replace_at_runtime):**
* 문제: `RewrittenYaml`이 런타임에 XML 경로를 제대로 찾지 못하는 환경적 결함.
* 해결: `total_patrol.launch.py` 내부에 Python 기반의 **YAML 사전 처리(Pre-processing)** 로직을 도입하여 경로 치환의 신뢰성을 100% 확보.

**19. 주행 중단(Status 5/6) 시 순찰 강제 종료:**
* 문제: 장애물 회피를 위한 주행 취소 발생 시 순찰 시퀀스가 완전히 멈춤.
* 해결: `get_result_callback` 로직을 개선하여 `ABORTED` 및 `CANCELED` 상태에서 순찰 플래그(`is_patrolling`)를 유지하도록 방어 코드 구축.

**20. 대기 시간 파라미터 하드코딩:**
* 문제: 장애물 및 AI 대기 시간이 코드에 고정되어 있어 실시간 조정 불가.
* 해결: 원격 서버(Web DB)의 설정값과 실시간 동기화하여 대시보드에서 즉시 제어 가능하게 함.

**21. 선반 이름 및 좌표 일관성 결여:**
* 문제: `shelf_1` 등 임시 이름을 사용하여 실제 환경 태그와의 매칭이 어려움.
* 해결: `TAG-A1-001` 등 표준 명칭을 키값으로 사용하고 실측 좌표 및 바코드를 YAML에 통합.

**22. AI 인식과 장애물 감지의 간섭:**
* 문제: 로봇이 AI 인식을 위해 가까이 멈췄을 때, 장애물 노드가 매대를 장애물로 오인하여 주행을 방해함.
* 해결: `/ai_mode_active` 토픽을 신설하여 AI 인식 시점에 장애물 감지 로직을 일시 정지(Pause)하도록 연동.

**23. DB 접속 정보 파편화:**
* 문제: 노드별로 API 주소와 포트 정보가 하드코딩되어 환경 변경 시 수정이 어려움.
* 해결: `InventoryDB` 패키지의 기본 접속 정보를 서버 표준(`:8000`)으로 일원화하고 모든 노드에서 이를 공유.

**24. AI 인식 데이터 수집 신뢰도:**
* 문제: 목적지 도착 직후 단 한 번의 비전 데이터만 확인하여 통신 지연이나 노이즈에 취약함.
* 해결: 최대 **8초간 폴링(Polling)** 하며 반복적으로 매칭 여부를 확인하는 고도화된 판정 로직 도입.

**25. 내비게이션 초기 위치 확신도:**
* 문제: `initialpose` 발행 시 공분산 없이 좌표만 전송하여 AMCL 초기 위치 보정이 느림.
* 해결: 공분산(`covariance`) 값을 최적화하여 위치 추정 정확도와 복구 속도를 대폭 개선.

**26. 매대 전면 방향(Yaw) 동기화 결여:**
* 문제: 맵 좌표(x, y)는 맞으나 로봇이 도착 후 엉뚱한 방향을 바라보아 AI 인식이 불가능함.
* 해결: 서버 DB에 `loc_yaw` 컬럼을 신설하고, 도착 지점의 Orientation 데이터를 연동하여 매대를 정확히 정면으로 바라보도록 동기화.

**27. AMCL 동기화 수동 의존성:**
* 문제: 노드 실행 후 매번 수동으로 초기 위치를 잡아주어야 주행이 가능함.
* 해결: 노드 시작 1초 후 자동으로 `(0,0,0)` 위치를 발행하는 **Auto Init** 타이머를 도입하여 시스템 기동 즉시 순찰 가능 상태로 전환.

**28. 내비게이션 중단상태(ABORTED) 수습 불가:**
* 문제: 경로 상의 일시적 문제로 Nav2가 포기(Aborted)하면 순찰 시퀀스가 거기서 멈춤.
* 해결: `ABORTED` 수신 시 자동으로 2초 대기 후 현재 목표를 재전송하는 **Retry Timer** 로직을 통해 주행 회복력 극대화.

**29. 실시간 영상 송출 지연(Camera Lag):**
* 문제: RTSP 스트림의 버퍼가 쌓여 대시보드 화면이 실제 로봇보다 수 초 뒤에 보이는 현상.
* 해결: 누적 버퍼를 강제로 비우는 **Buffer Clearing Loop**와 FPS 최적화(20 FPS)를 통해 실시간 캠 지연을 0.5초 미만으로 단축.

**30. 비상 제동 신뢰도 부족:**
* 문제: 단발성 `cmd_vel=0` 명령이 통신 혼선 등으로 무시되어 로봇이 계속 전진하는 상황 발생.
* 해결: 정지 명령 시 동일 메시지를 **5회 연속 발행(Aggressive Stop)** 하여 어떠한 상황에서도 확실한 제동이 이루어지도록 보강.

**31. 장애물 감지 노드 간섭 조절:**
* 문제: 주변 환경이나 로봇 팔 등의 구조물로 인해 장애물 노드가 주행을 과도하게 방해함.
* 해결: `total_patrol.launch.py`에 `run_obstacle_node` 인자를 추가하고, 런타임에 이 로직을 켜고 끌 수 있는 파라미터(`use_obstacle_avoidance`) 지원.

**32. 장애물 회피 로직 최적화 (LOGIC_01/02 통합):**
* 문제: 가상 벽(Virtual Wall) 및 강제 후진 로직이 AMCL 위치 추정 오차와 Nav2 경로 재계산 부하를 유발함.
* 해결: 강제 후진을 제거하고, `set_nav2_speed`를 활용해 파라미터 수준에서 속도를 제어(0.0/0.2)하도록 리팩토링함. 수동 조작 시 전방 감지 범위를 좁혀(±15°) 좁은 길 통과 성능을 개선함.

**33. 내비게이션 파라미터 표준화 및 순정화:**
* 문제: 여러 개발 단계에서 파라미터가 파편화되어 로봇의 거동이 예측 불가능해짐.
* 해결: `LOGIC_01_STOCK_NAV` 브랜치를 신설하고 제조사(TurtleBot3) 순정 파라미터(`inflation: 0.5`, `scaling: 5.0`)로 전수 동기화하여 기준점을 재정립함. `transform_tolerance` 강화로 위치 추정 신뢰도 확보.

**34. 통합 및 온디맨드 AI 비전 시스템 구축:**
* 문제: YOLO, QR, 검증 노드가 분산되어 중복 연산을 수행하고 주행 중에도 CPU를 과도하게 점유함.
* 해결: 모든 인식 로직을 `IntegratedPCNode`로 통합하여 프레임을 공유하고, `/ai_mode` 트리거를 도입하여 로봇이 매대 앞에 멈췄을 때만 연산이 활성화되는 온디맨드 시스템을 구축함.

**35. AI 인식 대기 시간 단축 및 타임아웃 문제:**
* 문제: 서버(DB)의 `avoidance_wait_time` 설정값이 너무 낮게 동기화되어, 로봇이 도착하자마자 인식을 포기하고 `TIMEOUT`을 발생시키는 현상.
* 해결: `patrol_node` 내에 최소 대기 시간 보장 로직을 추가하여, 서버 설정이 아무리 낮아도 최소 10초는 확정적으로 기다리도록 안전장치를 마련함.

**36. 통합 패키지 실행 파일 명칭 불일치:**
* 문제: AI 노드 통합 과정에서 `detector_node`라는 명칭이 사라졌으나, 상위 런치 파일(`total_patrol.launch.py`)에서 구형 명칭을 계속 호출하여 실행이 실패함.
* 해결: `total_patrol.launch.py` 내의 호출부를 `integrated_node`로 전수 최신화하고 패키지 재빌드를 통해 정합성을 맞춤.
</aside>
</aside>

---

## 📝 참조 가이드 (README_SLAM.md 본문)

```markdown
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
  map:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/maps/my_store_map_02.yaml \
  params_file:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/src/patrol_main/config/nav2_params.yaml
```
> [!IMPORTANT]
> 로봇 네임스페이스(예: `TB3_2`)를 사용 중인 경우, 모든 명령어 뒤에 `__ns:=/TB3_2` 옵션을 추가해야 할 수도 있습니다. 
```
