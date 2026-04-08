## 🚀 기능 개요

<aside>
💡 **기능명 : 순찰 관리 및 로봇 제어 통합 Python API (PatrolInterface)**
</aside>

<aside>
💡 **목적 :** UI 개발자가 ROS 2의 복잡한 토픽, 서비스, 파라미터 구조를 몰라도 단순한 파이썬 함수 호출만으로 **순찰 스케줄링, 로봇 수동 제어, 재고/알림 데이터 조회**를 수행하기 위함.
</aside>

---

## 📋 기능 명세 및 요구사항

<aside>
💡 **사용자 시나리오 :**

1.  UI 개발자가 `PatrolInterface` 인스턴스를 생성한다 (백그라운드 ROS 2 노드 및 서버 연동 스레드 자동 실행).
2. `move_robot("UP")`을 호출하여 수동 제어한다 (우선순위 기반 `/cmd_vel_teleop`).
3. `trigger_manual_patrol()` 또는 `return_to_base()`를 호출하여 자율 주행 시퀀스를 제어한다.
4. `get_inventory_data()` 및 `get_alarm_data()`를 통해 서버의 실시간 상품 현황을 UI 테이블에 투영한다.
5. 서버 대시보드에서 보낸 원격 명령(`START_PATROL`, `EMERGENCY_STOP` 등)이 로봇에서 즉각 실행된다.
</aside>

---

## 🛠️ 기술적 세부사항

<aside>
💡 **핵심 로직 및 동기화 :**

- **절대 경로 토픽 관리**: `/patrol_cmd`, `/patrol_status` 등 모든 주요 명령 토픽을 절대 경로로 설정하여 네임스페이스에 관계없이 통신 가능하도록 보장.
- **제어 우선순위 준수 (LOGIC_02)**: `twist_mux` 기반의 우선순위 체계를 적용하여, 내비게이션 중에도 `/cmd_vel_teleop` 토픽을 통해 즉각적인 수동 제어권을 확보.
- **세션 기반 순찰 관리**: `InventoryDB`를 통해 순찰 시작(`start_patrol_session`) 및 종료(`finish_patrol_session`) 시점을 서버와 동기화하여 정확한 순찰 이력 추적.
- **서버 및 바코드 연동 (Server)**: 로봇이 인식한 선반의 `tag_barcode`와 상품의 `detected_barcode`를 서버로 전송하는 바코드 기반 판독 시퀀스 지원.
- **원격 명령 폴링 (Remote Polling)**: 별도 스레드에서 서버의 최신 명령을 감시하고 로봇의 ROS 동작으로 즉각 매핑.
</aside>

---

## **📂 핵심 인터페이스 (Code)**

### **1. PatrolInterface 초기화 및 제어 토픽 설정**

```python
class PatrolInterface:
    def __init__(self, node_name='ui_patrol_interface'):
        # ... (중략) ...
        # 제어용 Publisher 및 Client (절대 경로 준수)
        self.teleop_pub = self.node.create_publisher(Twist, '/cmd_vel_teleop', 10)
        self.cmd_pub = self.node.create_publisher(String, '/patrol_cmd', 10)
        self.emergency_pub = self.node.create_publisher(Bool, '/emergency_stop', 10)
        
        # 서버 명령 폴링 스레드 (2.0s 간격)
        self.poll_thread = threading.Thread(target=self._poll_remote_commands, daemon=True)
        self.poll_thread.start()
```

### **2. 주요 제어 및 명령 인터페이스**

| 메서드명 | 설명 | 비고 |
| :--- | :--- | :--- |
| `move_robot(direction)` | 수동 이동 (UP/DOWN/LEFT/RIGHT/STOP) | `/cmd_vel_teleop` 발행 |
| `trigger_manual_patrol()` | 즉시 순찰 시작 명령 | `/patrol_cmd` (START_PATROL) |
| `return_to_base()` | 순찰 중단 및 원점 복귀 | `/patrol_cmd` (RETURN_HOME) |
| `reset_position()` | 내비게이션 위치 추정치 초기화 | `/patrol_cmd` (RESET_POSE) |
| `trigger_emergency_stop()` | 비상 정지 신호 즉시 발행 | `/emergency_stop` |
| `trigger_buzzer(state)` | 로봇 부저 제어 | `/robot_buzzer` |

### **3. 데이터 조회 및 구성 관리**

```python
def get_inventory_data(self):
    """서버에서 가공된 재고 리스트(6개 컬럼) 반환"""
    return self.db.get_inventory()

def get_recent_patrol_time(self):
    """최근 순찰 상태 및 시간 정보를 서버/ROS 토픽으로부터 취합"""
    # ROS 상태 우선 -> DB 이력 백업
    ...

def set_patrol_mode(self, mode):
    """순찰 모드 설정 (periodic / scheduled)"""
    return self._set_param('patrol_mode', mode, ParameterType.PARAMETER_STRING)
```

### **4. InventoryDB 서버 연동 명세**

| 메서드명 | 설명 | API End-point |
| :--- | :--- | :--- |
| `report_detection(...)` | 인식 결과 전송 (Tag + Product) | `POST /detections/add` |
| `start_patrol_session()` | 순찰 세션 시작 및 ID 획득 | `POST /patrol/start` |
| `finish_patrol_session()` | 진행 중인 순찰 세션 완료 처리 | `POST /patrol/finish` |
| `get_active_patrol_plan()` | 서버에 등록된 순찰 시퀀스 정보 조회 | `GET /patrol/plan` |

---

## 🎬 스크린샷 및 시연 영상

*   [시연 영상 1 - 자율 순찰 시작](https://youtu.be/D7ChdNX2pNQ)
*   [시연 영상 2 - 수동 제어 및 우선순위 전환](https://youtu.be/wPOUbHKJvJk)
*   [시연 영상 3 - 재고 판독 및 서버 동기화](https://youtu.be/HFpseVDnBQo)
*   [시연 영상 4 - 원격 명령 수신 및 처리](https://youtu.be/V_SuVqSbOak)

---

## 📈 이슈 및 특이사항 (Updates)

<aside>
💡 **v2.1 개선 사항 및 트러블슈팅 :**

1. **제어 토픽 우선순위 충돌**:
    * 문제: 기존 `/cmd_vel` 사용 시 Nav2 제어권과 충돌하여 수동 조작이 무시됨.
    * 해결: `LOGIC_02`의 `twist_mux` 규칙을 적용하여 우선순위가 높은 **`/cmd_vel_teleop`** 토픽으로 전송하도록 수정.
2. **상품 판독 메커니즘 변경**: 
    * 문제: 기존 Product ID 방식은 실제 환경의 오진열 및 결품 판정에 한계가 있음.
    * 해결: **바코드(Barcode)** 기반 판독 체계로 전환하여 서버에서 직접 데이터 정합성을 검증하도록 고도화.
3. **UI 테이블 데이터 규격 불일치**:
    * 문제: DB 원본 데이터와 UI 위젯(`QTableWidget`)이 요구하는 컬럼 수 및 형식이 다름.
    * 해결: `InventoryDB` 클래스 내에 **데이터 매퍼(Data Mapper)** 기능을 추가하여 6개(재고)/4개(알람) 컬럼 형식으로 자동 래핑.
4. **토픽 이름 충돌 및 절대 경로화**:
    * 문제: `patrol_node`와 `scheduler`가 서로 다른 네임스페이스에 있을 때 명령 미수신 발생.
    * 해결: `/patrol_cmd` 등 모든 제어 토픽을 **절대 경로**로 통일하여 해결.
5. **세션 종료 누락 방지**:
    * 문제: 순찰이 비정상 종료되거나 수동 중단될 때 서버 세션이 '진행 중'으로 남는 현상.
    * 해결: `patrol_node`의 중지 로직 및 `PatrolInterface`의 복귀 명령 시 `finish_patrol_session()`을 명시적으로 호출하도록 수정.
7. **PatrolInterface 초기화 오류 (AttributeError)**:
    * 문제: `last_command_execution_times` 속성이 생성자에서 초기화되지 않아 원격 명령 폴링 시 노드 크래시 발생.
    * 해결: `__init__` 함수에 해당 딕셔너리 명시적 초기화 추가 및 `processed_ids` 상태 관리 로직 강화.
8. **BT Navigator 경로 치환 실패 (replace_at_runtime)**:
    * 문제: `RewrittenYaml`이 중첩된 YAML 구조 내의 Behavior Tree XML 경로(문자열)를 안정적으로 치환하지 못함.
    * 해결: `total_patrol.launch.py`에서 Python `yaml` 라이브러리를 사용하여 런치 시점에 파일을 직접 읽어 경로를 강제 치환하고 임시 파일을 생성하는 방식으로 고도화.
</aside>
