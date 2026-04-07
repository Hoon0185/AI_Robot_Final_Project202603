# 아파치(Apache)와 FastAPI(Python) 연동 가이드: 리버스 프록시(Reverse Proxy) 구성

아파치(Apache) 웹서버와 FastAPI(Python)를 함께 사용하는 가장 효율적인 방법은 **리버스 프록시(Reverse Proxy)** 구성입니다. 아파치가 클라이언트의 요청을 먼저 받아 정적 파일을 처리하거나, 특정 경로(`/api`)의 요청을 로컬에서 실행 중인 FastAPI 프로세스로 전달하는 방식입니다.

## 1. 아파치와 FastAPI의 상호작용 원리

본 시스템(Gilbot Project)에서는 아파치가 정적 리소스 서빙과 보안 설정을 담당하고, FastAPI가 실시간 데이터 처리 및 로봇 제어 API를 담당합니다.

1.  **클라이언트 요청**: 사용자가 80(HTTP) 포트로 접속합니다.
2.  **아파치 수신 (Frontend 서빙)**: 아파치가 요청을 받아 먼저 `/var/www/html` 또는 지정된 경로(`web-ui/dist`)에 있는 정적 파일(HTML, CSS, JS)을 직접 클라이언트에게 보냅니다.
3.  **프록시 전달**: 요청 경로가 `/api/`로 시작하는 경우, 아파치는 이를 로컬에서 실행 중인 FastAPI 포트(예: 8000)로 전달합니다.
4.  **FastAPI 처리**: FastAPI는 비즈니스 로직(DB 연동, 로봇 상태 확인 등)을 수행하고 결과를 아파치에 반환합니다.
5.  **최종 응답**: 아파치가 클라이언트에게 JSON 데이터를 전달합니다.

## 2. 통합 단계별 가이드 (본 시스템 기준)

### 1단계: 아파치 프록시 모듈 활성화
아파치가 요청을 FastAPI로 넘겨주기 위해 필요한 모듈을 활성화합니다.

```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo systemctl restart apache2
```

### 2단계: FastAPI 애플리케이션 준비
FastAPI는 특정 포트에서 대기하고 있어야 합니다. 본 시스템의 `main.py`는 기본적으로 8000번 포트에서 실행됩니다.

```python
# web-server/main.py 예시
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Gilbot API Server is running"}

# 실행: uvicorn main:app --host 0.0.0.0 --port 8000
```

### 3단계: 아파치 가상 호스트(Virtual Host) 설정
아파치 설정 파일(`/etc/apache2/sites-enabled/gilbot.conf`)에 프록시 규칙을 정의합니다.

```apache
<VirtualHost *:80>
    ServerAdmin webmaster@localhost
    # Vite로 빌드된 프론트엔드 정적 파일 경로
    DocumentRoot /home/robot/final_ws/AI_Robot_Final_Project202603/web-ui/dist

    <Directory /home/robot/final_ws/AI_Robot_Final_Project202603/web-ui/dist>
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>

    # Proxy 설정: /api/ 요청을 로컬 8000번 포트의 FastAPI로 전달
    ProxyPreserveHost On
    ProxyPass /api/ http://127.0.0.1:8000/
    ProxyPassReverse /api/ http://127.0.0.1:8000/

    ErrorLog ${APACHE_LOG_DIR}/error.log
    CustomLog ${APACHE_LOG_DIR}/access.log combined
</VirtualHost>
```

### 4단계: 설정 적용 및 검증
설정 파일 저장 후 아파치를 재시작하여 변경 사항을 적용합니다.

```bash
sudo apache2ctl configtest  # "Syntax OK" 확인
sudo systemctl restart apache2
```

## 3. 효과적인 통합을 위한 최적화 팁

1.  **정적 자원 분리 (Frontend Serving)**: Vite(Node.js 기반 빌드 도구)로 생성된 `dist` 폴더를 아파치가 직접 서빙하도록 설정하여 FastAPI의 부하를 최소화합니다. 상세한 Vite 사용법은 [Vite 사용 안내서](./vite_usage_guide.md)를 참고하세요.
2.  **Systemd 활용 (프로세스 관리)**: 본 시스템에서는 Node.js의 PM2 대신 **Systemd**(`gilbot-backend.service`)를 사용하여 FastAPI 프로세스가 죽지 않고 자동으로 재시작되도록 관리합니다.
3.  **API 경로 통일**: 아파치에서 `/api/` 프리픽스를 사용하여 백엔드 요청을 명확히 구분함으로써 관리의 편의성을 높입니다.
4.  **보안 강화**: 외부에는 아파치의 80/443 포트만 노출하고, 8000번 포트(FastAPI)는 `127.0.0.1`로 바인딩하여 안전하게 보호합니다.

## 4. 로봇 HMI 접속 시 8000번 포트를 사용하는 이유

로봇에 장착된 터치 스크린(HMI)은 `http://[IP주소]:8000/hmi/`와 같이 아파치(80)가 아닌 **FastAPI의 8000번 포트로 직접 접속**합니다. 그 이유는 다음과 같습니다.

1.  **FastAPI 직접 서빙**: 본 시스템의 `main.py`에는 `/hmi` 경로로 정적 파일을 제공하는 설정(`app.mount("/hmi", ...)`)이 포함되어 있습니다. 즉, HMI 화면 데이터는 백엔드 서버가 직접 들고 있습니다.
    <details>
    <summary>💡 왜 HMI를 아파치가 아닌 FastAPI가 직접 서빙하는가?</summary>
    <ul>
        <li><b>환경 일치성 (Atomicity)</b>: HMI는 로봇 제어와 밀접하게 연동된 하드웨어 제어판입니다. 백엔드 로직과 HMI 파일을 하나의 프로세스(FastAPI)에 묶어둠으로써, 업데이트 시 버전 미스매치를 방지하고 시스템의 원자성을 보장합니다.</li>
        <li><b>CORS 문제 회피</b>: HMI 화면과 API 서버가 동일한 호스트/포트(8000)를 사용하면, 복잡한 교차 출처 리소스 공유(CORS) 설정 없이도 안정적인 통신이 가능합니다.</li>
        <li><b>지연 시간 최소화</b>: 로봇 내부의 키오스크 브라우저에서 로컬 프로세스로 직접 접속하므로, 아파치 프록시 계층을 한 번 더 거치는 오버헤드를 줄여 실시간 제어 반응성을 높입니다.</li>
        <li><b>배포 단순화</b>: 아파치 설정이 없는 환경이나 로컬 개발 시에도 <code>main.py</code> 하나만 실행하면 즉시 HMI 화면까지 확인하며 테스트할 수 있습니다.</li>
    </ul>
    </details>
2.  **프록시 설정의 범위**: 현재 아파치 설정(`gilbot.conf`)은 오로지 `/api/` 요청만을 8000번으로 넘겨주도록 되어 있습니다. 따라서 아파치 포트(80)로 `/hmi`에 접속하면 아파치는 해당 경로를 알지 못해 연결이 되지 않습니다.
3.  **구조적 분리 (Internal vs External)**:
    -   **포트 80 (Apache)**: 일반 웹 사용자용 "대문"입니다. Vite로 빌드된 고성능 프론트엔드 UI를 보여줍니다.
    -   **포트 8000 (FastAPI)**: 로봇 내부 및 관리용 "직통문"입니다. 로봇 조작에 특화된 HMI 화면을 지연 시간 없이(Proxy를 거치지 않고) 직접 제공합니다.
4.  **포트 번호의 명시**: 웹 브라우저는 기본적으로 80번(HTTP)으로 접속을 시도합니다. 8000번은 표준 포트가 아니므로, 아파치를 거치지 않고 백엔드 서버에 **직접(Direct)** 닿기 위해서는 반드시 주소 뒤에 `:8000`을 명시해 주어야 합니다.
