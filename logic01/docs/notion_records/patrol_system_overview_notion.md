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
1. **이벤트 기반 동적 스케줄러**: `parameter_callback`과 `update_config` 함수를 통해 순찰 간격이나 모드가 변경되는 즉시 시스템에 반영되도록 설계.
2. **Action 기반 정밀 내비게이션**: Nav2 액션 서버의 실시간 피드백을 수신하여 `GoalStatus`를 엄격히 검증하며, 특정 지점 도착 시 2초간 정지 후 다음 위치로 이동.
3. **SLAM 및 TF 정합성 해결**: `systemd-timesyncd` 중단 후 수동 시간 동기화를 통해 TF 에러를 해결하고, `slam_toolbox`를 활용하여 실시간 지도 생성을 최적화함.

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

### **2. Patrol Main Node (순차 방문 로직)**

```python
def get_result_callback(self, future):
    """내비게이션 결과 수신 및 바코드 판독 데이터 서버 전송"""
    self._goal_handle = None
    status = future.result().status
    if status == GoalStatus.STATUS_SUCCEEDED:
        # 바코드 판독 시퀀스 실행 및 DB 리포팅
        tag_barcode = self.shelves[shelf_name].get('tag_barcode', 'UNKNOWN')
        detected = self.simulate_barcode_scan() 
        self.db.report_detection(tag_barcode, detected, 0.98)
        
        self.get_logger().info(f'[{shelf_name}] 도착 및 판독 완료.')
        self.proceed_to_next_shelf() # 비차단형 타이머 기반 이동
    else:
        self.send_next_goal()
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
  map:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/maps/my_store_map_01.yaml \
  params_file:=$HOME/Documents/GitHub/AI_Robot_Final_Project202603/logic01/src/patrol_main/config/nav2_params.yaml
```
> [!IMPORTANT]
> 로봇 네임스페이스(예: `TB3_2`)를 사용 중인 경우, 모든 명령어 뒤에 `__ns:=/TB3_2` 옵션을 추가해야 할 수도 있습니다. 
```
