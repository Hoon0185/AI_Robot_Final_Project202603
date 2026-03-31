import os
import mysql.connector

try:
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
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
