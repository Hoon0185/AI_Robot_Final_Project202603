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
1. **Action 기반 정밀 내비게이션**: Nav2 액션 서버의 실시간 피드백을 수신하여 `GoalStatus`를 엄격히 검증하며, 특정 지점 도착 시 2초간 정지 후 다음 위치로 이동.
2. **ROS2 표준 YAML 구조 반영**: `/**: ros__parameters:` 중첩 구조를 적용하여 파라미터 서버와의 형식 불일치(`/shelf_1` vs `shelf_1`) 문제를 해결.
3. **지연 수신 대응 가이드**: WiFi 지연으로 인한 odom 에러 방지를 위해 커스텀 `nav2_params.yaml`을 사용하고, 도착 정밀도를 대폭 높임.

### **1. Patrol Main Node (순차 방문 로직)**

```python
def get_result_callback(self, future):
    """내비게이션 결과 수신 및 상태별 시퀀스 제어"""
    status = future.result().status
    if status == GoalStatus.STATUS_SUCCEEDED:
        self.get_logger().info(f'[{self.current_shelf_name}] 도착 완료. AI 검증 후 다음 지점으로.')
        self.proceed_to_next_shelf()
    elif status == GoalStatus.STATUS_ABORTED or status == GoalStatus.STATUS_CANCELED:
        # 장애물 우회 등으로 인한 중단 시, 순찰 종료 없이 대기 또는 재시도
        self.get_logger().warn('주행이 중단되었으나 순찰 상태를 유지합니다.')
    else:
        self.is_patrolling = False
        self.get_logger().error('회복 불가능한 주행 실패로 순찰을 중단합니다.')
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
</aside>

---

## 🖼️ 시각화 자료

- **Nav2 네비게이션 주행 및 목표 시각화**
![image.png](file:///home/penguin/Documents/GitHub/AI_Robot_Final_Project202603/DOCS_logic2/images/nav2_result.png)
*(참고: 이미지는 DOCS_logic2/images 폴더 내 파일을 참조합니다.)*
