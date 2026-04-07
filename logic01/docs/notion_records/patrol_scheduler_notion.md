## 🚀 기능 개요

<aside>
💡 **기능명 : 순찰 스케줄러 (Patrol Scheduler)**
목적 : 주기(Periodic), 특정 시각(Scheduled) 순찰뿐만 아니라 전용 서비스(Manual Trigger)를 통해 즉시 순찰을 수행할 수 있는 복합 스케줄링 로직 구현.
</aside>

---

## 📋 기능 명세 및 요구사항

<aside>
💡 **사용자 시나리오 :**
로봇이 배치되면, 시스템은 설정된 순찰 모드에 따라 자율 주행을 시작한다. 주기 모드에서는 정해진 시간 간격(분)마다, 예약 모드에서는 지정된 특정 시각(09:00, 15:00 등)마다 순찰이 수행된다. 긴급 상황 발생 시 UI를 통해 즉각적인 수동 순찰을 명령할 수 있으며, 이 모든 설정은 재부팅 없이 실시간으로 변경 가능하다.
</aside>

---

## 🛠️ 기술적 세부사항

💡 **핵심 로직:**
1. **이벤트 기반 동적 스케줄러**: `parameter_callback`과 `update_config` 함수를 통해 순찰 간격이나 모드가 변경되는 즉시 시스템에 반영되도록 설계.
2. **시계 감시(Clock Watchdog)**: 1Hz 주기의 타이머가 시스템 시각을 상시 연동하며 변경된 트리거 시점을 1초의 오차 없이 포착하도록 개선.
3. **비차단형 정차 로직**: 도착 후 2초간 정차할 때 `time.sleep` 대신 ROS 2 전용 타이머를 사용하는 비차단형 딜레이 로직 구현으로 노드 멈춤 현상 방지.

### **1. Patrol Scheduler (복합 모드 지원)**

```python
def update_config(self, params=None):
    """파라미터 변경 시 내부 설정(간격, 모드 등)을 즉시 업데이트"""
    if params:
        for param in params:
            if param.name == 'patrol_interval_min':
                self.interval_sec = float(param.value) * 60.0
            elif param.name == 'patrol_mode':
                self.mode = param.value
    else:
        # 초기화 시 현재 파라미터 값 로드
        self.mode = self.get_parameter('patrol_mode').value
        self.interval_sec = self.get_parameter('patrol_interval_min').value * 60.0
```

### **2. Manual Trigger Service**

```python
# scheduler 노드에 추가된 수동 시작 인터페이스
def manual_trigger_callback(self, request, response):
    self.trigger_patrol("Manual Service Call")
    response.success = True
    response.message = "Patrol started manually."
    return response
```

### **3. 파이썬 API 사용 가이드 (PatrolInterface)**

```python
from patrol_main.patrol_interface import PatrolInterface

# 인터페이스 초기화
patrol = PatrolInterface()

# 순찰 모드 및 설정 (변경 시 즉시 적용)
patrol.set_patrol_mode("periodic")
patrol.set_patrol_interval(30.0)

# 수동 순찰 즉시 실행 서비스 호출
patrol.trigger_manual_patrol()
```

---

## 📈 이슈 및 트러블슈팅

<aside>
💡 **v1.0 개발 노트 및 트러블슈팅 :**

1. **순찰 주기 변경 실시간 미반영**: 
    - 문제: 주기를 변경해도 다음 주기부터 적용되는 현상.
    - 해결: **Clock Watchdog** 로직 도입으로 1초마다 트리거 시점을 재계산하여 즉시 반영.
2. **런타임 노드 크래시**:
    - 문제: `time.sleep()` 사용으로 노드가 멈추거나 차단형 대기로 인한 통신 끊김 발생.
    - 해결: 전용 import 추가 및 ROS 2 타이머 기반의 **비차단형 딜레이** 로직 구현.
3. **동적 업데이트 시 부하**:
    - 문제: 반복적인 `get_parameter` 호출로 인한 데드락 및 데이털 병목 현상. 
    - 해결: 전용 `update_config` 함수를 통한 **이벤트 기반(On Set Parameter)** 업데이트 고도화.
</aside>

---

## 🎨 순찰 제어 인터페이스 활용

- **모드 전환 및 즉시 실행**
![image.png](file:///home/penguin/Documents/GitHub/AI_Robot_Final_Project202603/DOCS_logic2/images/patrol_scheduler.png)
*(참고: 이미지는 DOCS_logic2/images 폴더 내 파일을 참조합니다.)*
