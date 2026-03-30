## 기능 개요

<aside>
💡

기능명 : 순찰 관리 및 로봇 제어 통합 Python API (PatrolInterface)

</aside>

<aside>
💡

목적 : UI 개발자가 ROS 2의 복잡한 토픽, 서비스, 파라미터 구조를 몰라도 단순한 파이썬 함수 호출만으로 **순찰 스케줄링, 로봇 수동 제어, 재고/알림 데이터 조회**를 수행하기 위함.

</aside>

---

## 기능 명세 및 요구사항 (최신 업데이트)

<aside>
💡

사용자 시나리오 : 
1. UI 개발자가 `PatrolInterface` 인스턴스를 생성한다 (백그라운드 ROS 2 노드 자동 실행).
2. `move_robot("UP")`을 호출하여 로봇을 앞방향으로 이동시킨다 (Teleop 제어).
3. `trigger_emergency_stop()`을 호출하여 비상 상황 시 로봇을 즉각 정지시킨다.
4. `get_inventory_data()`를 호출하여 서버 또는 로컬 DB에서 최신 재고 목록(6개 컬럼)을 가져와 UI 테이블에 표시한다.
5. `get_alarm_data()`를 호출하여 재고 부족 알림 목록(4개 컬럼)을 UI에 띄운다.

</aside>

---

## 기술적 세부사항

<aside>
💡

핵심 로직 및 동기화 : 
- **제어 우선순위 준수 (LOGIC_02)**: `twist_mux` 설정에 따라 수동 조작 시 `/cmd_vel_nav`가 아닌 **`/cmd_vel_teleop`** 토픽을 사용하여 내비게이션 중에도 즉각적인 제어권을 확보.
- **서버 및 바코드 연동 (Server)**: 로봇이 선반의 `tag_barcode`와 상품의 `detected_barcode`를 판독하여 서버(`/v1/robot/inventory`)로 전송하는 시퀀스를 지원.
- **하이브리드 DB 연동**: `InventoryDB` 모듈을 통해 서버 API(FastAPI) 연동을 우선 시도하며, 서버 미응답 시 로컬 `inventory.json` 캐시 데이터를 반환하는 Fallback 로직 구현.

</aside>

---

## 핵심 인터페이스 (Code)

### **1. 초기화 및 제어 토픽 설정**

```python
class PatrolInterface:
    def __init__(self, node_name='ui_patrol_interface'):
        self.node = Node(node_name)
        # DB 연동 초기화 (Server/Local JSON)
        self.db = InventoryDB(base_url="http://localhost:8000")
        
        # 제어용 Publisher 초기화
        self.teleop_pub = self.node.create_publisher(Twist, '/cmd_vel_teleop', 10)
        self.buzzer_pub = self.node.create_publisher(Bool, '/robot_buzzer', 10)
        self.emergency_pub = self.node.create_publisher(Bool, '/emergency_stop', 10)
        
        # 비동기 스레드 구동
        self.executor = rclpy.executors.SingleThreadedExecutor()
        self.spin_thread = threading.Thread(target=self.executor.spin, daemon=True)
        self.spin_thread.start()
```

### **2. 로봇 제어 및 상태 관리**

```python
def move_robot(self, direction: str):
    """/cmd_vel_teleop 토픽 발행을 통한 방향키 제어"""
    # UP, DOWN, LEFT, RIGHT, STOP 처리 로직 포함
    ...
    self.teleop_pub.publish(twist)

def trigger_emergency_stop(self):
    """비상 정지 신호(/emergency_stop) 즉시 발행"""
    msg = Bool(data=True)
    self.emergency_pub.publish(msg)
```

### **3. 데이터 조회 (DB 연동)**

```python
def get_inventory_data(self):
    """서버/로컬 DB에서 재고 리스트(6개 컬럼) 반환"""
    return self.db.get_inventory()

def get_alarm_data(self):
    """서비/로컬 DB에서 알림 리스트(4개 컬럼) 반환"""
    return self.db.get_alarms()
```

---

## 이슈 및 특약 사항 (v2.0 업데이트)

<aside>
💡

**변경 사항 01**: 제어 토픽 변경 (`/cmd_vel` -> `/cmd_vel_teleop`). `LOGIC_02`의 우선순위 제어 노드와의 호환성을 위함.
**변경 사항 02**: 데이터 모델 변경. 기존 상품 ID 방식에서 **바코드(Barcode)** 기반 판독 및 전송 체계로 전환 (서버 브랜치 업데이트 반영).
**변경 사항 03**: `InventoryDB` 모듈 신규 추가. UI 테이블 규격(6개/4개 컬럼)에 맞춘 데이터 변환 레이어 구현.

</aside>

<aside>
💡

**주의**: 로봇의 물리적 비상 정지는 `/emergency_stop` 토픽을 하드웨어 드라이버 측에서 최종 가로채어 처리해야 함.

</aside>
