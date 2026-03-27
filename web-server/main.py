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
    total_waypoints: int = 0
    completed_waypoints: int = 0
    new_slots: int = 0
    moved_slots: int = 0
    missing_slots: int = 0

class Product(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    barcode: str
    category: str = "General"
    standard_qty: int = 0

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
            INSERT INTO patrol_log (start_time, end_time, status, total_waypoints, completed_waypoints, new_slots, moved_slots, missing_slots)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (patrol.start_time, patrol.end_time, patrol.status, patrol.total_waypoints, patrol.completed_waypoints, patrol.new_slots, patrol.moved_slots, patrol.missing_slots)
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

@app.get("/inventory")
async def list_inventory():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        # slot 테이블과 product_master를 바코드 기반으로 결합하여 상세 정보 조회
        query = """
            SELECT s.*, p.product_name, p.category 
            FROM slot s
            LEFT JOIN product_master p ON s.barcode = p.barcode
            ORDER BY s.last_updated DESC
        """
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    # 외부 IP 허용 및 포트 8000 실행
    uvicorn.run(app, host="0.0.0.0", port=8000)
