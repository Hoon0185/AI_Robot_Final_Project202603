import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def check_db(name):
    host = os.getenv("DB_HOST", "16.184.56.119")
    print(f"\n--- [ {name} @ {host} ] 데이터베이스 점검 시작 ---")
    try:
        connection = mysql.connector.connect(
            host=host,
            user=os.getenv("DB_USER", "gilbot"),
            password=os.getenv("DB_PASSWORD", "robot123"),
            database=os.getenv("DB_NAME", "gilbot")
        )
        if connection.is_connected():
            cursor = connection.cursor()
            # 1. 테이블 목록 확인
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"테이블 목록: {tables}")

            # 2. 각 테이블 구조 확인
            if tables:
                for table in tables:
                    table_name = table[0]
                    print(f"\n'{table_name}' 테이블 구조:")
                    cursor.execute(f"DESCRIBE {table_name}")
                    for row in cursor.fetchall():
                        print(row)
        
    except Error as e:
        print(f"연결 실패: {e}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()

if __name__ == "__main__":
    check_db('Gilbot Central DB')
