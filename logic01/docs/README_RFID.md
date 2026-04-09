# RFID 위치 보정 및 부저 제어 가이드 (RFID & Buzzer Guide)

이 문서는 RFID 태그를 이용한 **정밀 위치 보정(Landmark Localization)** 및 **로봇 부저(Buzzer)** 제어 방법을 설명합니다.

---

## 🚀 퀵 실행 (독립형 센서 노드) - 로봇 본체
라즈베리 파이에서 직접 실행하여 AMCL 위치 추정이 틀어지는 것을 방지합니다.
```bash
# 1. 로봇(SSH) 접속 후 rfid 폴더 이동
ssh penguin@192.168.0.3
cd ~/rfid

# 2. 독립형 RFID/부저 노드 실행
python3 standalone_rfid_buzzer.py
```
> [!NOTE]
> `standalone_rfid_buzzer.py`는 빌드 과정 없이 하드웨어에서 즉시 실행 가능하도록 설계되었습니다.

---

## 1. RFID 랜드마크 보정 원리
AMCL은 대칭 구조의 매장 환경에서 위치를 놓치기 쉽습니다. Gilbot은 선반 등에 부착된 RFID 태그를 **절대 좌표(Landmark)**로 인식하여 위치를 강제 보정합니다.

1. **태그 인식**: 로봇 하단의 RFID 리더가 태그를 인식합니다.
2. **좌표 매핑**: 태그 ID에 매핑된 지도상의 `(x, y, yaw)` 좌표를 가져옵니다.
3. **위치 업데이트**: `/initialpose` 토픽으로 고신뢰도 위치 정보를 발행하여 AMCL 위치를 즉시 동기화합니다.

---

## 2. 홈 태그(Home Tag) 및 좌표 관리
태그의 실제 지도 좌표는 `standalone_rfid_buzzer.py` 내부의 `self.landmark_map`에서 관리합니다.

- **표준 원점 (Home)**: 태그 ID `428801199154`는 지도의 **(0.0, 0.0)**으로 설정되어 있습니다. 로봇 기동 시 이 태그 위에서 시작하면 위치가 자동으로 잡힙니다.
- **좌표 업데이트**: 신규 선반이나 태그 추가 시 `shelf_coords.yaml`의 값을 참고하여 맵에 등록하세요.

| 태그 ID | 위치 설명 | 좌표 (x, y) |
| :--- | :--- | :--- |
| **428801199154** | **Home Base** | **(0.0, 0.0)** |
| 291971004317 | Shelf 3 | (-1.0189, -0.2340) |

---

## 3. 통합 부저 제어 (Buzzer System)
Gilbot은 PC의 관리 UI에서 직접 터틀봇3의 부저를 제어할 수 있습니다.

- **작동 기작**: 
    1. PC UI에서 `/robot_buzzer` (Bool) 토픽 발행.
    2. 로봇의 `standalone_rfid_buzzer.py`가 이를 구독.
    3. 터틀봇3 하드웨어의 `/sound` (Sound.msg)로 신호 변환 및 사운드 출력.
- **동작 확인**: UI에서 부저 버튼 클릭 시 로봇에서 **3회 비프음**이 발생하는지 확인하세요.

---

## 4. 트러블슈팅 (RFID/Localization)

### A. "Landmark Corrected!" 로그가 뜨지 않을 때
- 로봇 하단의 RFID 리더기와 태그 사이의 거리가 2cm 이내인지 확인하세요.
- `python3 standalone_rfid_buzzer.py` 실행 시 권한 에러(GPIO)가 발생하는지 터미널 로그를 체크하세요.

### B. 보정 후 로봇 위치가 튀는 현상
- `landmark_map`에 등록된 좌표와 실제 지도상의 위치가 일치하는지 확인하세요. (`clicked_point`로 재추출 권장)
- `/initialpose`의 공분산(Covariance) 값이 너무 크면 AMCL이 이를 무시할 수 있으므로, 현재 코드의 `0.05` 설정을 유지하세요.

---

 더 자세한 관리 시스템 구동 방식은 **../../SJH_backup/SYSTEM_MANAGEMENT_GUIDE.md**를 함께 참고하세요.
