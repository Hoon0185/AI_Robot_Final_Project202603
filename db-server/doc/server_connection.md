# 🖥️ 서버 접속 정보

> **보안 주의:** 이 파일은 공개 접속 방법만 기록합니다. 비밀번호/토큰은 포함하지 않습니다.

---

## AWS Lightsail 서버 (gilbot DB 서버)

| 항목 | 값 |
|---|---|
| **IP** | `16.184.56.119` |
| **내부 IP** | `172.26.6.199` |
| **OS** | Ubuntu 24.04.4 LTS |
| **User** | `ubuntu` |
| **SSH Alias** | `ls` |
| **DB** | MySQL 8.0 / `gilbot` |

---

## SSH 접속

### 빠른 접속 (설정 완료 후)
```bash
ssh ls
```

### `.ssh/config` 설정 내용
```
Host ls
    HostName 16.184.56.119
    User ubuntu
    IdentityFile ~/.ssh/id_jalanwang_github
```

### 설정 방법 (최초 1회)
```bash
# 공개키 등록
ssh-copy-id ubuntu@16.184.56.119

# config 추가
cat >> ~/.ssh/config << 'EOF'
Host ls
    HostName 16.184.56.119
    User ubuntu
    IdentityFile ~/.ssh/id_jalanwang_github
EOF
chmod 600 ~/.ssh/config
```

---

## MySQL 접속

```bash
# Lightsail 서버에 SSH 접속 후
ssh ls
sudo mysql -u root -p

# 또는 한 줄로
ssh ls "sudo mysql -u root -p gilbot"
```

### 주요 명령어
```sql
USE gilbot;
SHOW TABLES;
DESCRIBE slot;
```

---

## 로봇(TurtleBot) 접속

| 항목 | 값 |
|---|---|
| **IP** | `192.168.1.200` |
| **User** | `robot` |
| **SSH Alias** | `tb` |

```bash
ssh tb
```

---

## 관련 파일

| 파일 | 설명 |
|---|---|
| [`create_tables.sql`](./create_tables.sql) | DB 테이블 생성 SQL |
| [`erd.md`](./erd.md) | ERD 다이어그램 |
| [`slot_update_logic.md`](./slot_update_logic.md) | 슬롯 자동 업데이트 로직 |
