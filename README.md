## AI_Robot_Final_Project202603
AI 로봇 프로그래밍 최종 팀 프로젝트입니다.

### 파일 용도
main.py : main문

robot_logic.py : 클라이언트에서 실질적으로 실행되는 메인로직. 작업자들이 구현,작성한 클래스를 각 함수 내에서 호출하도록 하는 형태

robot_login.py : 로그인 화면 UI

robot_ui.py : 메인 화면 UI

## 기획

## 사용자 시나리오

## 기능 명세서

## 개발 규칙 (Development Rules)

- **커밋 메시지**: 본 워크스페이스의 모든 Git 커밋 메시지는 반드시 **한글**로 작성합니다.
    - 예: `feat: 로봇 위치 추적 모듈 추가`, `fix: 인식 로그 저장 오류 수정`
- **코드 주석**: 주요 로직에는 한글 주석을 남겨 이해를 돕습니다.
- **배포 방식**: `git pull` -> `npm install` (필요시) -> `npm run build` (UI 수정시) -> `systemctl restart gilbot-backend.service` (백엔드 수정시)
