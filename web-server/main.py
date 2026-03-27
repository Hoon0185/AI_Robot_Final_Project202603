import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import List, Optional
from pydantic import BaseModel
import mysql.connector
from mysql.connector import Error

# 환경 변수 로드 (.env 파일이 있으면 읽어옴)
load_dotenv()

app = FastAPI(
    title="Gilbot API Server",
    description="편의점 매대 관리 로봇(Gilbot) 제어를 위한 백엔드 서버",
    version="0.2.3",
    root_path="/api"
)

# CORS 설정: 프론트엔드(React 등)의 접속을 허용합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실무에서는 ["http://localhost:3000"] 처럼 특정 주소만 넣는 것을 권장합니다.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 데이터 모델 정의 (Pydantic)
class PatrolInsert(BaseModel):
    start_time: str
    end_time: Optional[str] = None
    status: str = "완료"
    scanned_slots: int = 0
    error_found: int = 0

class Product(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    barcode: str
    category: str = "General"
    standard_qty: int = 0

class PatrolConfig(BaseModel):
    avoidance_wait_time: int
    patrol_start_time: str
    patrol_end_time: str
    interval_hour: int
    interval_minute: int
    is_active: bool = True

class PatrolConfig(BaseModel):
    avoidance_wait_time: int
    patrol_start_time: str
    patrol_end_time: str
    interval_hour: int
    interval_minute: int
    is_active: bool = True

# 데이터베이스 연결 함수
def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "gilbot"),
            charset="utf8mb4"
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

@app.get("/")
async def root():
    return {
        "message": "Welcome to Gilbot API Server",
        "docs": "/docs",
        "env": "production" if os.getenv("DB_HOST") == "16.184.56.119" else "local"
    }

@app.get("/status")
async def get_status():
    conn = get_db_connection()
    db_status = "connected" if conn and conn.is_connected() else "disconnected"
    if conn:
        conn.close()

    return {
        "status": "running",
        "database": db_status,
        "db_host": os.getenv("DB_HOST")
    }

@app.get("/patrol/list")
async def list_patrols():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM patrol_log ORDER BY patrol_id DESC LIMIT 10")
        results = cursor.fetchall()
        return results
    finally:
        if conn:
            conn.close()

# --- Patrol Log Admin API ---

@app.post("/patrol/add")
async def add_patrol(patrol: PatrolInsert):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO patrol_log (start_time, end_time, status, scanned_slots, error_found)
            VALUES (%s, %s, %s, %s, %s)
        """
        values = (patrol.start_time, patrol.end_time, patrol.status, patrol.scanned_slots, patrol.error_found)
        cursor.execute(query, values)
        conn.commit()
        return {"message": "Patrol log added successfully", "id": cursor.lastrowid}
    except Error as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.delete("/patrol/{patrol_id}")
async def delete_patrol(patrol_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM patrol_log WHERE patrol_id = %s", (patrol_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Log not found")
        return {"message": "Patrol log deleted successfully"}
    finally:
        conn.close()

# --- Product Master Admin API ---

@app.get("/products")
async def list_products():
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM product_master ORDER BY product_id DESC")
        return cursor.fetchall()
    finally:
        conn.close()

@app.post("/products/add")
async def add_product(product: Product):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = "INSERT INTO product_master (product_name, barcode, category, standard_qty) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (product.product_name, product.barcode, product.category, product.standard_qty))
        conn.commit()
        return {"message": "Product added successfully", "id": cursor.lastrowid}
    finally:
        conn.close()

# --- v3.1 New Endpoints ---

@app.get("/alerts")
async def list_alerts():
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT a.*, p.product_name, w.waypoint_name
            FROM alert a
            LEFT JOIN product_master p ON a.product_id = p.product_id
            LEFT JOIN waypoint w ON a.waypoint_id = w.waypoint_id
            WHERE a.is_resolved = FALSE
            ORDER BY a.alert_id DESC
        """
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        conn.close()

@app.get("/detections")
async def list_detections():
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT d.*, p.product_name 
            FROM detection_log d
            LEFT JOIN product_master p ON d.product_id = p.product_id
            ORDER BY d.log_id DESC LIMIT 50
        """
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        conn.close()

@app.get("/inventory")
async def list_inventory():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        # v3.1 스키마에 맞춘 현재 매대 상태 조회
        query = """
            SELECT ss.*, p.product_name, w.waypoint_name
            FROM shelf_status ss
            LEFT JOIN product_master p ON ss.product_id = p.product_id
            LEFT JOIN waypoint w ON ss.waypoint_id = w.waypoint_id
            ORDER BY ss.last_updated_at DESC
        """
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    # 외부 IP 허용 및 포트 8000 실행
    uvicorn.run(app, host="0.0.0.0", port=8000)
