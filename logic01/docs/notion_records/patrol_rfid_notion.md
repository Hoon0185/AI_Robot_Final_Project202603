## 🚀 기능 개요

<aside>
💡 **기능명 : RFID 기반 랜드마크 위치 보정 (Robust Localization)**
목적 : AMCL의 고질적인 문제인 누적 오차 및 대칭 환경에서의 위치 상실(Kidnapped Robot Problem)을 물리적 랜드마크(RFID)를 통해 강제로 해결.
</aside>

---

## 📋 기능 명세 및 요구사항

<aside>
💡 **사용자 시나리오 :**
로봇이 순찰 중 진열대(Shelf) 앞에 도착하면, 바닥이나 진열대에 부착된 RFID 태그를 읽는다. AMCL이 추정한 현재 위치와 태그에 기록된 실제 좌표가 다를 경우, 시스템은 즉시 좌표를 수정하여 내비게이션의 정밀도를 복구한다. 특히 WiFi 신호 불안정으로 인한 Odom 튀는 현상 발생 시 결정적인 보정 역할을 수행한다.
</aside>

---

## 🛠️ 기술적 세부사항

💡 **핵심 로직:**
1. **태그-좌표 매핑 하드코딩**: 특정 RFID UID를 지도상의 절대 좌표 `(x, y, yaw)`로 매핑하여 데이터베이스화.
2. **비차단형 RFID 리딩**: `SimpleMFRC522`의 `read_no_block()`을 사용하여 로봇의 메인 루프를 방해하지 않고 지속적으로 태그 감시.
3. **AMCL 강제 주입(`/initialpose`)**: `PoseWithCovarianceStamped` 메시지를 통해 매우 낮은 공분산(Covariance) 값을 부여함으로써 AMCL이 해당 위치를 신뢰하도록 강력한 힌트 제공.
4. **디바운싱(Cooldown)**: 동일 태그가 짧은 시간 내 여러 번 인식될 경우 발생하는 중복 보정 방지(3초 쿨다운).

### **1. RFID Localization Node (핵심 보정 로직)**

```python
def publish_initial_pose(self, tag_id):
    coords = self.landmark_map[tag_id]
    msg = PoseWithCovarianceStamped()
    msg.header.stamp = self.get_clock().now().to_msg()
    msg.header.frame_id = 'map'
    
    # 위치 및 방향 설정
    msg.pose.pose.position.x = coords['x']
    msg.pose.pose.position.y = coords['y']
    msg.pose.pose.orientation.z = math.sin(coords['yaw'] / 2.0)
    msg.pose.pose.orientation.w = math.cos(coords['yaw'] / 2.0)
    
    # 높은 신뢰도 부여 (공분산 최소화)
    msg.pose.covariance = [0.0] * 36
    msg.pose.covariance[0] = 0.05   # x 분산 
    msg.pose.covariance[7] = 0.05   # y 분산
    msg.pose.covariance[35] = 0.05  # yaw 분산
         
    self.initial_pose_pub.publish(msg)
```

### **2. 런치 파일 통합 (Launch Integration)**

```python
# run_rfid 인자에 따른 조건부 실행
Node(
    package='patrol_main',
    executable='rfid_localization_node',
    name='rfid_localization_node',
    condition=IfCondition(run_rfid)
)
```

---

## 📈 이슈 및 특이사항

<aside>
💡 **v1.0 개발 노트 및 트러블슈팅 :**

1. **GPIO 권한 및 충돌**: 
    - 문제: `RPi.GPIO` 모듈 사용 시 권한 에러 발생.
    - 해결: 실행 계정을 `gpio` 그룹에 추가하거나 `sudo` 권한 체크 로직 검토.
2. **태그 인식 거리 이슈**:
    - 문제: 리더기가 바닥과 너무 멀면 인식이 안 됨.
    - 해결: 로봇 하단 프레임에 연장 브라켓을 설치하여 태그와의 거리를 2cm 이내로 조정.
3. **좌표 불일치로 인한 오작동**:
    - 문제: 실제 위치와 매핑된 좌표가 조금만 틀어져도 AMCL이 벽 속으로 들어가는 현상.
    - 해결: `clicked_point` 토픽을 활용하여 실측 좌표를 정밀하게 재추출하여 반영.
4. **시뮬레이션 환경 테스트 불가**:
    - 참고: 하드웨어 의존적이므로 Gazebo 환경에서는 `run_rfid:=false`로 두고 수동으로 `/initialpose`를 발행하여 로직 검증.
</aside>
