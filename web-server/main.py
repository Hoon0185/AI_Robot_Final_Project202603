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
    version="0.2.4",
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

class DetectionInput(BaseModel):
    tag_barcode: str
    detected_barcode: Optional[str] = None
    confidence: float = 0.0
    odom_x: float = 0.0
    odom_y: float = 0.0
    timestamp: str

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

@app.post("/patrol/finish")
async def finish_patrol():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        # 진행 중인 가장 최근 순찰 찾기
        cursor.execute("SELECT patrol_id FROM patrol_log WHERE status = '진행중' ORDER BY start_time DESC LIMIT 1")
        patrol = cursor.fetchone()
        if not patrol:
            raise HTTPException(status_code=404, detail="No active patrol found to finish")
        
        patrol_id = patrol['patrol_id']
        cursor.execute(
            "UPDATE patrol_log SET status = '완료', end_time = NOW() WHERE patrol_id = %s",
            (patrol_id,)
        )
        conn.commit()
        return {"message": "Patrol finished successfully", "patrol_id": patrol_id}
    finally:
        conn.close()

@app.post("/patrol/stop")
async def stop_patrol():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT patrol_id FROM patrol_log WHERE status = '진행중' ORDER BY start_time DESC LIMIT 1")
        patrol = cursor.fetchone()
        if not patrol:
            raise HTTPException(status_code=404, detail="No active patrol found to stop")
        
        patrol_id = patrol['patrol_id']
        cursor.execute(
            "UPDATE patrol_log SET status = '중단', end_time = NOW() WHERE patrol_id = %s",
            (patrol_id,)
        )
        conn.commit()
        return {"message": "Patrol stopped (Emergency)", "patrol_id": patrol_id}
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

@app.post("/detections/add")
async def add_detection(data: DetectionInput):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 1. 진행 중인 최신 순찰 회차 조회
        cursor.execute("SELECT patrol_id FROM patrol_log WHERE status = '진행중' ORDER BY start_time DESC LIMIT 1")
        patrol = cursor.fetchone()
        if not patrol:
            # 진행중인 게 없으면 그냥 '완료'된 최신이라도 찾거나 에러
            cursor.execute("SELECT patrol_id FROM patrol_log ORDER BY start_time DESC LIMIT 1")
            patrol = cursor.fetchone()
        
        patrol_id = patrol['patrol_id'] if patrol else 1 # 기본값 1 (테스트용)

        # 2. 태그 바코드로 해당 위치(슬롯) 및 계획된 상품 조회
        # slot과 waypoint_product_plan을 조인하여 '있어야 할 상품'을 찾음
        query_plan = """
            SELECT s.slot_id, s.waypoint_id, p.product_id as planned_product_id
            FROM slot s
            JOIN waypoint_product_plan p ON s.slot_id = p.slot_id
            WHERE s.barcode_tag = %s
        """
        cursor.execute(query_plan, (data.tag_barcode,))
        slot_plan = cursor.fetchone()
        
        if not slot_plan:
             raise HTTPException(status_code=404, detail=f"Tag barcode {data.tag_barcode} not found in plan")
        
        slot_id = slot_plan['slot_id']
        waypoint_id = slot_plan['waypoint_id']
        planned_product_id = slot_plan['planned_product_id']

        # 3. 인식된 바코드로 실제 상품 ID 조회
        detected_product_id = None
        if data.detected_barcode:
            cursor.execute("SELECT product_id FROM product_master WHERE barcode = %s", (data.detected_barcode,))
            prod = cursor.fetchone()
            if prod:
                detected_product_id = prod['product_id']

        # 4. 판독 로직 (정상 / 없음 / 오진열)
        result_status = '정상'
        if not data.detected_barcode:
            result_status = '없음'
        elif detected_product_id != planned_product_id:
            result_status = '오진열'

        # 5. shelf_status 업데이트 (현재 매대 현황)
        # 해당 슬롯에 대한 레코드가 이미 있는지 확인
        cursor.execute("SELECT status_id FROM shelf_status WHERE slot_id = %s", (slot_id,))
        existing_status = cursor.fetchone()
        
        if existing_status:
            update_status_sql = "UPDATE shelf_status SET product_id = %s, status = %s, last_updated_at = NOW() WHERE slot_id = %s"
            cursor.execute(update_status_sql, (detected_product_id or planned_product_id, result_status, slot_id))
        else:
            insert_status_sql = "INSERT INTO shelf_status (waypoint_id, slot_id, product_id, status) VALUES (%s, %s, %s, %s)"
            cursor.execute(insert_status_sql, (waypoint_id, slot_id, detected_product_id or planned_product_id, result_status))

        # 6. detection_logInsert (인식 이력 기록)
        insert_log_sql = """
            INSERT INTO detection_log (patrol_id, waypoint_id, slot_id, product_id, detected_barcode, tag_barcode, confidence, result, odom_x, odom_y)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_log_sql, (patrol_id, waypoint_id, slot_id, detected_product_id, data.detected_barcode, data.tag_barcode, data.confidence, result_status, data.odom_x, data.odom_y))

        # 7. Alert 생성 (이상 감제 시)
        if result_status != '정상':
            alert_msg = f"{data.tag_barcode} 위치: 계획된 상품과 다름" if result_status == '오진열' else f"{data.tag_barcode} 위치: 상품 없음"
            insert_alert_sql = """
                INSERT INTO alert (patrol_id, waypoint_id, slot_id, product_id, alert_type, message)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_alert_sql, (patrol_id, waypoint_id, slot_id, planned_product_id, result_status, alert_msg))

        # 8. patrol_log 통계 업데이트
        update_patrol_sql = "UPDATE patrol_log SET scanned_slots = scanned_slots + 1, error_found = error_found + %s WHERE patrol_id = %s"
        cursor.execute(update_patrol_sql, (1 if result_status != '정상' else 0, patrol_id))

        conn.commit()
        return {
            "status": "success", 
            "judgment": result_status, 
            "slot_id": slot_id,
            "slot_info": f"Waypoint {waypoint_id}, Slot {slot_id}",
            "patrol_id": patrol_id
        }

    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
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

@app.get("/patrol/config")
async def get_patrol_config():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        # TIME 컬럼은 스트링으로 가져와야 프론트엔드 input[time]에서 제대로 인식함
        cursor.execute("""
            SELECT 
                config_id, avoidance_wait_time, 
                CAST(patrol_start_time AS CHAR) as patrol_start_time, 
                CAST(patrol_end_time AS CHAR) as patrol_end_time,
                interval_hour, interval_minute, is_active
            FROM patrol_config 
            ORDER BY config_id DESC LIMIT 1
        """)
        config = cursor.fetchone()
        if not config:
            # 기본 설정값 반환
            return {
                "avoidance_wait_time": 5,
                "patrol_start_time": "09:00:00",
                "patrol_end_time": "22:00:00",
                "interval_hour": 1,
                "interval_minute": 0,
                "is_active": True
            }
        return config
    finally:
        conn.close()

@app.post("/patrol/config")
async def update_patrol_config(config: PatrolConfig):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO patrol_config 
            (avoidance_wait_time, patrol_start_time, patrol_end_time, interval_hour, interval_minute, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (
            config.avoidance_wait_time, config.patrol_start_time, 
            config.patrol_end_time, config.interval_hour, 
            config.interval_minute, config.is_active
        )
        cursor.execute(query, values)
        conn.commit()
        return {"message": "Config updated successfully", "id": cursor.lastrowid}
    finally:
        conn.close()

@app.get("/patrol/plan")
async def get_patrol_plan():
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                p.plan_id, p.waypoint_id, p.slot_id, p.product_id,
                w.waypoint_name, s.barcode_tag, s.row_num,
                m.product_name, m.barcode as product_barcode
            FROM waypoint_product_plan p
            LEFT JOIN waypoint w ON p.waypoint_id = w.waypoint_id
            LEFT JOIN slot s ON p.slot_id = s.slot_id
            LEFT JOIN product_master m ON p.product_id = m.product_id
            ORDER BY w.waypoint_id, s.slot_id
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
