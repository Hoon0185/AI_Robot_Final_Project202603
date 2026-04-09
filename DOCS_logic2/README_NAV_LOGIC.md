# 🤖 내비게이션 커스텀 제어 가이드 (Nav2 Logic Custom)

이 섹션은 로봇의 주행 및 장애물 회피 로직을 최적화하기 위해 **Nav2 소스 코드를 직접 수정**한 내용과 빌드 지침을 다룹니다.

## 1. 빌드 및 설치 (Build Guide)
순정 Nav2 대신 수정된 커스텀 로직을 적용하기 위해 반드시 아래 순서대로 빌드해야 합니다.

```bash
cd ~/Documents/GitHub/AI_Robot_Final_Project202603/logic01

# 1. 의존성 패키지 설치 (최초 1회 필수)
rosdep update && rosdep install --from-paths src --ignore-src -r -y

# 2. 커스텀 패키지 포함 전체 빌드
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

# 3. 환경 변수 등록 (내 워크스페이스 우선순위 확보)
source install/setup.bash
```

> [!CAUTION]
> **반드시 `source install/setup.bash`를 실행하세요.**
> 이 과정을 생략하면 시스템에 설치된 기본 Nav2가 실행되어 커스텀 로직(장애물 회피 등)이 작동하지 않습니다.

---

## 2. 빌드 오류 해결 (Troubleshooting)

빌드 과정에서 문제가 발생할 경우 아래 순서대로 조치하십시오.

1. **의존성 미설치 (`Package not found`)**
   * 해결: 상단의 `rosdep install` 명령어를 다시 실행하여 누락된 라이브러리를 설치합니다.
2. **메모리 부족으로 인한 멈춤 (`C++ 컴파일러 종료`)**
   * 해결: `colcon build --parallel-workers 1` 옵션을 사용하여 패키지를 하나씩 순차적으로 빌드합니다.
3. **이전 빌드와의 충돌 (`CMake Cache Error`)**
   * 해결: `rm -rf build/ install/ log/` 명령어로 기존 빌드 기록을 완전히 삭제한 후 다시 빌드합니다.
4. **로직 수정이 반영 안 됨**
   * 해결: 소스 코드(`.cpp`, `.hpp`)를 수정했다면 반드시 다시 `colcon build`를 수행해야 바이너리에 반영됩니다.

---

## 3. 커스텀 적용 확인
터미널에 아래 명령어를 입력하여 현재 어느 경로의 Nav2를 사용하는지 확인합니다.
```bash
ros2 pkg prefix nav2_controller
```
* **성공**: `/home/.../logic01/install/nav2_controller` (내 폴더 경로)
* **실패**: `/opt/ros/humble/...` (이 경우 `source` 다시 실행)
