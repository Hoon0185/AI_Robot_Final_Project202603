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
    """내비게이션 결과 수신 및 성공 여부 판단"""
    result = future.result()
    if result.status == GoalStatus.STATUS_SUCCEEDED:
        self.get_logger().info(f'[{self.current_shelf_name}] 도착 완료.')
        self.wait_at_shelf() # 도착 후 비차단형 대기 실행
    else:
        # 장애물 등으로 인한 주행 실패 시에도 복구(skip) 로직 수행
        self.get_logger().warn('이동 실패. 다음 목표로 진행합니다.')
        self.send_next_goal()
```

### **2. ROS2 표준 YAML 구조 (shelf_coords.yaml)**

```yaml
/**:
  ros__parameters:
    shelves:
      shelf_1: {x: 0.5, y: 0.0, yaw: 0.0}
      shelf_2: {x: 1.2, y: -0.5, yaw: 1.57}
      # ... (중합 구조를 통한 표준 파라미터 호환성 확보)
```

---

## 📈 이슈 및 트러블슈팅

<aside>
💡 **v1.0 개발 노트 및 트러블슈팅 :**

1. **내비게이션 논리적 버그**:
    - 문제: 장애물 등으로 주행 실패 시에도 무조건 "도착"으로 간주하고 정지 시간을 가지는 현상.
    - 해결: `GoalStatus.STATUS_SUCCEEDED` 상태값만 필터링하도록 로직 강화.
2. **Nav2 서버 연결 안정성**:
    - 문제: 서버 준비 전 목표 전송 시 노드 멈춤 현상 발생.
    - 해결: `wait_for_server()` 방어 코드를 추가하여 연결 확인 후 주행 명령 전송.
3. **네임스페이스(TB3_2) 환경 정합성**:
    - 문제: 프레임 이름 하드코딩으로 인한 데이터 단절 발생.
    - 해결: 명령어 실행 시 `__ns:=/TB3_2` 옵션 및 전용 런칭 파일 작성 필수 적용.
4. **Humble 버전 플러그인 로딩 에러**:
    - 문제: Nav2 파라미터 내 플러그인 구분자(`::`) 불일치로 인한 크래시.
    - 해결: 구분자를 `/`로 전면 수정하여 로딩 실패 해결.
</aside>

---

## 🖼️ 시각화 자료

- **Nav2 네비게이션 주행 및 목표 시각화**
![image.png](file:///home/penguin/Documents/GitHub/AI_Robot_Final_Project202603/DOCS_logic2/images/nav2_result.png)
*(참고: 이미지는 DOCS_logic2/images 폴더 내 파일을 참조합니다.)*
