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

## 4. 🚀 AWS Lightsail 실전 배포 버전

실전 서버(AWS)는 유저명이 `ubuntu`이며, 폴더 경로가 다를 수 있습니다. 아래 설계도를 참조하세요.

### 설계도 (/etc/systemd/system/gilbot-backend.service)
```ini
[Unit]
Description=Gilbot FastAPI Backend Service
After=network.target mysql.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/AI_Robot_Final_Project202603/web-server
ExecStart=/usr/bin/python3 /home/ubuntu/AI_Robot_Final_Project202603/web-server/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## 5. 💡 주의사항 (로컬 vs 실전)
- **유저명**: 로컬은 `robot`, 실전은 `ubuntu`입니다.
- **경로**: 로컬은 `/home/robot/...`, 실전은 `/home/ubuntu/...` 입니다.
- **포트**: 8000번 포트가 이미 사용 중이라면, 실전에서도 `sudo fuser -k 8000/tcp`로 청소 후 엔진을 부팅하세요.
