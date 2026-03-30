import os
import mysql.connector
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

try:
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST", "16.184.56.119"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "gilbot"),
        password=os.getenv("DB_PASSWORD", "robot123"),
        database=os.getenv("DB_NAME", "gilbot"),
        charset="utf8mb4"
    )
    cursor = connection.cursor(dictionary=True)
    cursor.execute("DESCRIBE shelf_status;")
    print("shelf_status:", cursor.fetchall())
    cursor.execute("DESCRIBE waypoint_product_plan;")
    print("waypoint_product_plan:", cursor.fetchall())
except Exception as e:
    print(e)
