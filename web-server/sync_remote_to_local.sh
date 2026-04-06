#!/bin/bash

# .env 파일 로드
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
fi

echo "--- [ Gilbot DB Sync: REMOTE -> LOCAL ] ---"
echo "Remote Host: $REMOTE_DB_HOST"
echo "Local Host: $LOCAL_DB_HOST"
echo "------------------------------------------"

read -p "원격 DB 데이터를 로컬 DB($LOCAL_DB_HOST)로 가져오시겠습니까? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "동기화를 취소합니다."
    exit 1
fi

# 원격 DB 덤프
echo "1. 원격 DB($REMOTE_DB_HOST) 추출 중..."
mysqldump -h $REMOTE_DB_HOST -u $REMOTE_DB_USER -p$REMOTE_DB_PASSWORD $REMOTE_DB_NAME > /tmp/gilbot_remote_backup.sql

if [ $? -eq 0 ]; then
    echo "   [성공] 원격 데이터 추출 완료."
else
    echo "   [실패] 원격 데이터 추출 중 오류 발생."
    exit 1
fi

# 로컬 DB 반영
echo "2. 로컬 DB로 데이터 쓰기 중..."
mysql -h $LOCAL_DB_HOST -u $LOCAL_DB_USER -p$LOCAL_DB_PASSWORD $LOCAL_DB_NAME < /tmp/gilbot_remote_backup.sql

if [ $? -eq 0 ]; then
    echo "   [성공] 로컬 DB 동기화 완료!"
else
    echo "   [실패] 로컬 DB 반영 중 오류 발생."
    exit 1
fi

# 임시 파일 삭제
rm /tmp/gilbot_remote_backup.sql

echo "------------------------------------------"
echo "원격 데이터를 로컬로 성공적으로 가져왔습니다."
