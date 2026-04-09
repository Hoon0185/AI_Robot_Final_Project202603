# Gilbot Logic01: 하이브리드 지능형 순찰 시스템

`Logic01` 패키지는 실시간 서버 동기화, RFID 기반 위치 보정, 그리고 AI 객체 인식이 통합된 길봇(Gilbot)의 핵심 두뇌입니다. 하이브리드 동기화 전략을 통해 최소한의 리소스로 최신의 순찰 설정을 로봇에 반영합니다.

---

## 📂 상세 문서 인덱스 (Documentation)
모든 상세 가이드는 **[docs/](./docs/)** 폴더 내에 체계적으로 정리되어 있습니다.

1.  **[시스템 작동 가이드 (README_OPERATION.md)](./docs/README_OPERATION.md)**
    *   로봇 기동, 순찰 제어, AI 및 UI 연계 통합 실행 절차 안내.
2.  **[순찰 스케줄러 및 API 상세 (README_PATROL.md)](./docs/README_PATROL.md)**
    *   하이브리드 동기화(Reconfig), 순찰 계획 관리, Python API 사용법 기술.
3.  **[RFID 보정 및 부저 시스템 (README_RFID.md)](./docs/README_RFID.md)**
    *   RFID를 이용한 정밀 위치 보정 원리 및 UI 통합 부저 제어 방법 설명.
4.  **[SLAM 및 지도 제작 가이드 (README_SLAM.md)](./docs/README_SLAM.md)**
    *   매장 지도 생성(SLAM), 좌표 추출 및 내비게이션 환경 설정 안내.
5.  **[노션 업무 기록 (notion_records/)](./docs/notion_records/)**
    *   개발 과정에서의 핵심 이슈 및 히스토리 보관함.

---

## 🛠️ 핵심 특징 (Key Features)

- **하이브리드 동기화 (Hybrid Sync)**: 서버 부하를 줄이기 위해 초기 Polling 후 이벤트 기반(`RECONFIG`, `START_PATROL`)으로 설정을 갱신합니다.
- **장애물 회피(LOGIC_02) 통합**: `logic2_pkg`의 장애물 감지 및 우회 시퀀스가 순찰 노드와 완벽하게 조화되었습니다.
- **실시간 좌표 동기화**: DB에 기록되는 로봇의 최신 x, y 좌표를 UI 미니맵 위젯과 1초 주기로 연동합니다.
- **AI 멀티 모달 인식**: YOLOv8 기반 상품 인식과 바코드 스캔 결과를 교차 검증하여 순찰 리포트를 생성합니다.

---

## 🚀 빠른 시작 (Quick Start)
```bash
# 워크스페이스 빌드
colcon build --symlink-install

# 통합 순찰 시스템 실행
ros2 launch patrol_main total_patrol.launch.py use_ai_sim:=false
```

---

*   전체 프로젝트 관리 흐름은 **[SJH_backup/SYSTEM_MANAGEMENT_GUIDE.md](../SJH_backup/SYSTEM_MANAGEMENT_GUIDE.md)**를 참고하십시오.
