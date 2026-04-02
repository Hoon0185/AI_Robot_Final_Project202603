## 🚀 기능 개요

<aside>
💡 **기능명 : SLAM 및 맵핑 (SLAM & Mapping)**
목적 : SLAM Toolbox를 활용한 정밀 맵 생성 및 Lidar frame_id 최적화를 통한 데이터 정합성 확보.
</aside>

---

## 📋 기능 명세 및 요구사항

<aside>
💡 **사용자 시나리오 :**
로봇이 처음 환경에 배치되면, 운영자는 SLAM 모드를 활성화하여 매장의 지도를 생성한다. 이때 로봇과 PC 간의 시간 차이로 인한 TF 에러를 방지하기 위해 정밀한 시간 동기화가 선행되어야 하며, 완성된 지도는 향후 내비게이션의 기초 데이터로 저장된다.
</aside>

---

## 🛠️ 기술적 세부사항

💡 **핵심 로직 및 인프라 설정:**
1. **SLAM 및 TF 정합성 해결**: `systemd-timesyncd` 중단 후 PC 시각 기반의 수동 시간 동기화(`date -s`)를 통해 AMCL 및 SLAM의 위치 유실 방지.
2. **Lidar frame_id 최적화**: `/base_scan` 등 선행 슬래시 포함으로 인한 호환성 에러를 해결하기 위해 `frame_id:=base_scan`으로 강제 할당.
3. **QoS 최적화**: RViz "No map received" 이슈 해결을 위해 QoS 설정을 `Transient Local`로 변경하여 지연 수신 데이터 처리.

### **1. 시간 동기화 및 Bringup 가이드**

```bash
# 1. 로봇(SSH)에서 자동 동기화 중지
ssh penguin@<ROBOT_IP> "echo robot123 | sudo -S systemctl stop systemd-timesyncd"

# 2. PC 시간을 로봇에 강제 주입 (PC 터미널에서 실행)
ssh penguin@<ROBOT_IP> "echo robot123 | sudo -S date -s '@$(date +%s)'"

# 3. 로봇 기체 실행 (Bringup)
ros2 launch turtlebot3_bringup robot.launch.py
```

### **2. SLAM Toolbox 실행 및 맵 저장**

```bash
# SLAM 실행 (PC)
ros2 launch slam_toolbox online_async_launch.py use_sim_time:=false

# 맵 저장 (map_saver_cli 사용)
ros2 run nav2_map_server map_saver_cli -f ~/my_store_map_01
```

---

## 📈 이슈 및 트러블슈팅

<aside>
💡 **v1.0 개발 노트 및 트러블슈팅 :**

1. **로봇-PC 간 시간 동기화(TF_OLD_DATA)**:
    - 문제: 미세한 시간 차이(1초 미만)로 인해 SLAM 위치가 사라지거나 에러 지속 발생.
    - 해결: `systemd-timesyncd` 중지 후 수동 동기화 가이드 적용하여 TF 정합성 100% 확보.
2. **SLAM 방식 비교 및 최적화**:
    - 문제: Cartographer 사용 시 연결 불안정 및 낮은 해상도 이슈 발생.
    - 해결: **SLAM Toolbox** 방식으로 전환하여 정밀도 및 실시간성 확보.
3. **RViz 시각화 이슈 (No map received)**:
    - 문제: 맵 토픽은 정상이나 RViz에서 지도가 표시되지 않음.
    - 해결: QoS 설정을 `Transient Local`로 변경하여 해결.
4. **Lidar frame_id 호환성 에러**:
    - 문제: `/base_scan`의 슬래시 제거 필요.
    - 해결: 런칭 파일에서 `frame_id:=base_scan`으로 강제 할당.
</aside>

---

## 🖼️ 시각화 자료

- **Namespace(TB3_2) + Cartographer SLAM**
![스크린샷 2026-03-24 15-02-30.png](file:///home/penguin/Documents/GitHub/AI_Robot_Final_Project202603/DOCS_logic2/images/스크린샷_2026-03-24_15-02-30.png)
*(참고: 이미지는 DOCS_logic2/images 폴더 내 파일을 참조합니다.)*
