#!/bin/bash

# .env 파일 로드
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
fi

echo "--- [ Gilbot DB Sync: LOCAL -> REMOTE ] ---"
echo "Mode: $DB_MODE"
echo "Local Host: $LOCAL_DB_HOST"
echo "Remote Host: $REMOTE_DB_HOST"
echo "------------------------------------------"

read -p "로컬 DB 데이터를 원격 DB($REMOTE_DB_HOST)로 덮어쓰시겠습니까? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "동기화를 취소합니다."
    exit 1
fi

# 로컬 DB 덤프 (데이터 + 스키마)
echo "1. 로컬 DB 덤프 중..."
mysqldump -h $LOCAL_DB_HOST -u $LOCAL_DB_USER -p$LOCAL_DB_PASSWORD $LOCAL_DB_NAME > /tmp/gilbot_local_backup.sql

if [ $? -eq 0 ]; then
    echo "   [성공] 로컬 데이터 추출 완료."
else
    echo "   [실패] 로컬 데이터 추출 중 오류 발생."
    exit 1
fi

# 원격 DB 반영
echo "2. 원격 DB($REMOTE_DB_HOST)로 데이터 전송 중..."
mysql -h $REMOTE_DB_HOST -u $REMOTE_DB_USER -p$REMOTE_DB_PASSWORD $REMOTE_DB_NAME < /tmp/gilbot_local_backup.sql

if [ $? -eq 0 ]; then
    echo "   [성공] 원격 DB 동기화 완료!"
else
    echo "   [실패] 원격 DB 반영 중 오류 발생."
    exit 1
fi

# 임시 파일 삭제
rm /tmp/gilbot_local_backup.sql

echo "------------------------------------------"
echo "동기화가 완료되었습니다."
