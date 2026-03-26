# 🚀 Gilbot FastAPI 백엔드 무한 가동 (Systemd) 가이드

이 문서는 FastAPI 서버를 백그라운드 서비스로 등록하여, 터미널을 종료해도 서버가 계속 작동하게 만드는 방법을 설명합니다.

## 1. 서비스 파일 생성
아래 내용을 `/etc/systemd/system/gilbot-backend.service` 경로에 생성합니다.

```ini
[Unit]
Description=Gilbot FastAPI Backend Service
After=network.target mysql.service

[Service]
User=robot
Group=robot
WorkingDirectory=/home/robot/final_ws/AI_Robot_Final_Project202603/web-server
ExecStart=/usr/bin/python3 /home/robot/final_ws/AI_Robot_Final_Project202603/web-server/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## 2. 엔진 관리 부대 명령어
설정 후 아래 명령어를 순차적으로 실행하여 엔진을 활성화합니다.

1. **설정 새로고침**: `sudo systemctl daemon-reload`
2. **자동 시작 등록**: `sudo systemctl enable gilbot-backend`
3. **서비스 시작**: `sudo systemctl start gilbot-backend`
4. **상태 확인**: `sudo systemctl status gilbot-backend`

## 3. 왜 사용하나요?
- **상시 가동**: 터미널 창을 닫아도 서버가 죽지 않습니다.
- **자동 복구**: 서버 내부 에러로 프로세스가 죽으면 Systemd가 즉시 다시 살려냅니다.
- **부팅 시 자동 실행**: 서버 장비를 껐다 켜도 자동으로 엔진이 돌아갑니다.
