import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# .env 로드
load_dotenv()

def create_table():
    db_mode = os.getenv("DB_MODE", "local").lower()
    
    # 설정값 추출
    host = os.getenv(f"{db_mode.upper()}_DB_HOST", "localhost")
    port = int(os.getenv(f"{db_mode.upper()}_DB_PORT", 3306))
    user = os.getenv(f"{db_mode.upper()}_DB_USER", "gilbot")
    pw = os.getenv(f"{db_mode.upper()}_DB_PASSWORD", "robot123")
    db_name = os.getenv(f"{db_mode.upper()}_DB_NAME", "gilbot")

    print(f"Connecting to {db_mode} database at {host}...")

    try:
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=pw,
            database=db_name,
            charset="utf8mb4"
        )
        cursor = conn.cursor()
        
        # 테이블 생성 쿼리
        query = """
        CREATE TABLE IF NOT EXISTS activity_log (
            log_id INT AUTO_INCREMENT PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source ENUM('robot', 'user', 'web_server', 'db_server', 'system') NOT NULL,
            target ENUM('robot', 'user', 'web_server', 'db_server', 'all') NOT NULL,
            activity_type ENUM('COMMAND', 'RESPONSE', 'NOTIFICATION', 'ERROR', 'STATUS_CHANGE', 'BOOT') NOT NULL,
            action VARCHAR(100),
            payload JSON,
            message TEXT,
            status ENUM('SUCCESS', 'FAILED', 'PENDING') DEFAULT 'SUCCESS'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        cursor.execute(query)
        conn.commit()
        print("✅ [SUCCESS] activity_log table created or already exists.")
        
    except Error as e:
        print(f"❌ [ERROR] Failed to create table: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    create_table()
