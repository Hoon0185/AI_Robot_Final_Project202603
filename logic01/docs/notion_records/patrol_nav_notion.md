## 🚀 기능 개요

<aside>
💡 **기능명 : 웨이포인트 내비게이션 및 시각화 (Navigation & Visualization)**
목적 : ROS 2 표준 파라미터 구조(`YAML`)를 사용하여 진열대 좌표를 유연하게 관리하고, RViz 상에서 실시간으로 마커(MarkerArray)를 가시화하여 순찰 경로의 직관성 제공.
</aside>

---

## 📋 기능 명세 및 요구사항

<aside>
💡 **사용자 시나리오 :**
로봇은 전용 순찰 맵 위에서 미리 정의된 진열대(Shelf) 좌표를 따라 자율 주행한다. 운영자는 `shelf_coords.yaml` 파일을 수정하는 것만으로 새로운 지점을 추가하거나 변경할 수 있으며, 주행 중인 로봇의 다음 목표는 RViz 상에 초록색 구체와 태그 이름으로 즉시 표시되어 모니터링이 용이해진다.
</aside>

---

## 🛠️ 기술적 세부사항

💡 **핵심 로직:**
1. **Action 기반 정밀 내비게이션**: Nav2 액션 서버의 실시간 피드백을 수신하여 `GoalStatus`를 엄격히 검증하며, `ABORTED`(5) 또는 `CANCELED`(6) 수신 시 순찰을 중단하지 않고 3초간 대기 후 재전송하거나 상태를 보존함.
2. **매대 전면 방향(Yaw) 동기화**: 서버 DB의 `loc_yaw` 데이터를 연동하여, 로봇이 도착 후 단순히 서 있는 것이 아니라 매대를 정확히 정면으로 바라보도록 로직 고도화.
3. **위치 추정 정밀도 및 안정성**: `initialpose` 자동 발행(Auto Init) 타이머를 제거하여 실제 바닥 마찰 및 센서 튀는 현상으로 인한 오차 누적을 방지하고, AMCL `transform_tolerance`를 0.5s로 강화.
4. **표트 표준 파라미터 적용**: 터틀봇3 제조사 순정 설정(`inflation_radius: 0.5`, `cost_scaling_factor: 5.0`)을 적용하여 좁은 길 통과 안정성 보장.

### **1. Patrol Main Node (상태 기반 주행 제어)**

```python
def get_result_callback(self, future):
    """내비게이션 결과 수신 및 주행 중단 상황 방어 로직 (v0.0.18+)"""
    status = future.result().status
    if status == GoalStatus.STATUS_SUCCEEDED:
        # 정상 도착 시 AI 검증 시퀀스 시작
        self.trigger_ai_detection(shelf_name)
    elif status == GoalStatus.STATUS_ABORTED:
        # 일시적 경로 문제 시 3초 후 재시도
        self.retry_timer = self.create_timer(3.0, self._trigger_retry)
    elif status == GoalStatus.STATUS_CANCELED:
        # 취소 시 순찰 시퀀스 유지 (장애물 회피 등)
        self.get_logger().warn('Navigation canceled. Maintaining patrol state.')
```

### **2. ROS2 표준 YAML 구조 (shelf_coords.yaml)**

```yaml
/**:
  ros__parameters:
    shelves:
      TAG-A1-001: 
        tag_barcode: '8801043036436'
        waypoint_id: 2
        x: -0.5233, y: -0.2373, yaw: 0.0
      TAG-A1-002: 
        tag_barcode: '8801111611312'
        waypoint_id: 3
        x: 0.4778, y: -0.1872, yaw: 0.0
```

---

## 📈 이슈 및 트러블슈팅

<aside>
💡 **v1.0 개발 노트 및 트러블슈팅 :**

5. **주행 중단 대응 결함**:
    - 문제: 장애물 회피를 위한 자발적 취소(CANCELED) 시에도 전체 순찰이 중단되는 현상.
    - 해결: `STATUS_CANCELED` 및 `ABORTED` 상태를 예외 처리하여 순찰 시퀀스를 보존함.
6. **좌표 및 태그 명칭 불일치**:
    - 문제: DB와 로컬 YAML 간의 이름(shelf_1 vs TAG-A1-001) 불일치로 인한 혼동.
    - 해결: DB의 표준 명칭으로 YAML 키를 통일하고 AMCL 실측 좌표를 반영함.
7. **순정 파라미터 이탈 및 주행 위화감**:
    - 문제: 커스텀 최적화 중 순정 상태에서 너무 멀어져 로봇 거동이 불안정해짐.
    - 해결: `LOGIC_01_STOCK_NAV` 브랜치 신설 및 공식 TB3 파라미터(0.5/5.0)로 원복하여 안정성 검증 완료.
</aside>

---

## 🖼️ 시각화 자료

- **Nav2 네비게이션 주행 및 목표 시각화**
![image.png](file:///home/penguin/Documents/GitHub/AI_Robot_Final_Project202603/DOCS_logic2/images/nav2_result.png)
*(참고: 이미지는 DOCS_logic2/images 폴더 내 파일을 참조합니다.)*
