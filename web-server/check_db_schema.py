import mysql.connector
from mysql.connector import Error

def check_db(host, name):
    print(f"\n--- [{name}] 데이터베이스 점검 시작 ---")
    try:
        connection = mysql.connector.connect(
            host=host,
            user='gilbot',
            password='robot123',
            database='gilbot'
        )
        if connection.is_connected():
            cursor = connection.cursor()
            # 1. 테이블 목록 확인
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"[{name}] 테이블 목록: {tables}")

            # 2. patrol_log 테이블 구조 확인 (가장 중요한 테이블)
            if tables:
                for table in tables:
                    table_name = table[0]
                    print(f"\n[{name}] '{table_name}' 테이블 구조:")
                    cursor.execute(f"DESCRIBE {table_name}")
                    for row in cursor.fetchall():
                        print(row)
        
    except Error as e:
        print(f"[{name}] 연결 실패: {e}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()

# 1. 로컬 체크 (127.0.0.1)
check_db('127.0.0.1', 'LOCAL')
