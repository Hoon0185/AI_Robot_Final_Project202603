# 🚀 Gilbot AWS Lightsail 배포 가이드 (Deployment Guide)

이 문서는 Gilbot 시스템을 AWS Lightsail 환경에 배포하는 상세 절차와 관리 방법을 설명합니다.

---

## 1. 서버 사양 및 환경 정보 (Infrastructure)

- **클라우드 서비스**: AWS Lightsail
- **운영체제**: Ubuntu 22.04 LTS
- **네트워크 설정**:
  - `80 (HTTP)`: Apache2를 통한 관리자 웹 UI 서빙
  - `443 (HTTPS)`: (선택 사항) 인증서 적용 시 사용
  - `8000 (TCP)`: FastAPI 백엔드 API 서버 포트 (Apache 프록시 연동: `/api` -> `8000`)
  - `22 (SSH)`: 원격 관리용 (IP: `16.184.56.119`)

---

## 2. 배포 프로세스 (Deployment Workflow)

이 시스템은 **Git**을 사용하여 로컬 환경의 코드를 원격 서버에 동기화하고, 각 서비스를 수동으로 재기동하는 방식으로 배포됩니다.

### **Step 1: 로컬 작업 내용 반영 (Push)**
로컬 작업이 완료된 후, 변경 사항을 GitHub 원격 저장소로 보냅니다.
```bash
# 로컬 터미널에서 실행
git push origin server
```

### **Step 2: 원격 서버 코드 업데이트 (Pull)**
SSH를 통해 Lightsail 인스턴스에 접속하여 최신 소스 코드를 가져옵니다.
```bash
# SSH 접속 (구성된 별칭 'ls' 사용 가능)
ssh ls

# 프로젝트 폴더 이동 및 풀(Pull)
cd /home/ubuntu/AI_Robot_Final_Project202603
git pull origin server
```

### **Step 3: 프론트엔드 빌드 및 정적 파일 배포**
Vite(React) 결과물을 빌드하여 Apache가 참조하는 `dist` 폴더를 갱신합니다.
```bash
cd /home/ubuntu/AI_Robot_Final_Project202603/web-ui
npm install      # 의존성 패키지 설치
npm run build    # 빌드 (결과물은 dist/ 폴더에 생성)
```
*참고: Apache 설정(`/etc/apache2/sites-enabled/gilbot.conf`)에 의해 빌드 즉시 웹에서 반영됩니다.*

### **Step 4: 백엔드 API 서버 재기동**
Python 기반 FastAPI 백엔드 서비스를 재시작하여 새로운 로직을 적용합니다.
```bash
# systemd 서비스 재시작
sudo systemctl restart gilbot-backend.service

# 서비스 상태 확인
sudo systemctl status gilbot-backend.service
```

---

## 3. 서비스 구성 요소 상세 (Service Architecture)

| 컴포넌트 | 역할 | 상세 실행 방식 |
| :--- | :--- | :--- |
| **백엔드 (FastAPI)** | API 및 명령 관리 | `systemd` 서비스 (`gilbot-backend.service`)로 자동 실행 |
| **프론트엔드 (React)** | 사용자 인터페이스 | `Apache2` 웹 서버가 `/web-ui/dist`의 정적 파일 서빙 |
| **DB (MySQL)** | 데이터 저장 | 로컬 MySQL 서비스 (`3306` 포트) |
| **Reverse Proxy** | 경로 제어 | Apache의 `ProxyPass` 기능을 이용해 `/api` 요청을 `8000`번 포트로 전달 |

---

## 4. 트러블 슈팅 (Troubleshooting)

배포 중 발생할 수 있는 주요 문제와 해결 방법입니다. (진행 후 실재 사례를 바탕으로 업데이트 예정)

1.  **Apache 404/503 Error**:
    - `ProxyPass` 설정 확인: `/etc/apache2/sites-enabled/gilbot.conf`에서 백엔드 주소(`127.0.0.1:8000`)가 맞는지 확인.
    - 백엔드 서비스 생존 여부: `sudo systemctl status gilbot-backend.service`로 확인.
2.  **npm build 실패**:
    - 메모리 부족: Lightsail 사양이 1GB 이하일 경우 빌드 중 멈출 수 있습니다. 이 경우 로컬 빌드 후 `dist` 폴더만 전송하는 방식을 고려해야 합니다.
3.  **DB 연결 오류**:
    - `.env` 파일의 비밀번호 및 DB 이름이 서버의 MySQL 설정과 일치하는지 확인.

---

*작성일: 2026-03-30*
