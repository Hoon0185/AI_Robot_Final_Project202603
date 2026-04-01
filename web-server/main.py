import os
from datetime import datetime
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
    version="0.3.0",
    root_path="/api"
)

# CORS 설정: 프론트엔드(React 등)의 접속을 허용합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 인메모리 로봇 상태 저장용 (DB 테이블 생성 전까지 사용) ---
class RobotStatusStore:
    def __init__(self):
        self.last_heartbeat = None
        self.last_x = 0.0
        self.last_y = 0.0

global_robot_status = RobotStatusStore()

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
    min_inventory_qty: int = 5
    yolo_class_id: Optional[int] = None

class InventoryUpdate(BaseModel):
    current_inventory_qty: int

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
    yolo_class_id: Optional[int] = None
    confidence: float = 0.0
    odom_x: float = 0.0
    odom_y: float = 0.0
    timestamp: str

class UnifiedRegisterInput(BaseModel):
    product_name: str
    product_barcode: str
    category: str = "General"
    min_inventory_qty: int = 5
    waypoint_name: str
    row_num: int = 1
    yolo_class_id: Optional[int] = None

class PlanAddInput(BaseModel):
    waypoint_id: int
    barcode_tag: str
    row_num: int = 1
    product_id: int

class WaypointOrderUpdate(BaseModel):
    waypoint_id: int
    visit_order: int

class PlanOrderUpdate(BaseModel):
    plan_id: int
    plan_order: int

class WaypointUpdate(BaseModel):
    waypoint_no: int
    waypoint_name: str
    loc_x: float
    loc_y: float

# 데이터베이스 연결 함수
def get_db_connection():
    db_mode = os.getenv("DB_MODE", "local").lower()
    
    if db_mode == "remote":
        config = {
            "host": os.getenv("REMOTE_DB_HOST", "16.184.56.119"),
            "port": int(os.getenv("REMOTE_DB_PORT", 3306)),
            "user": os.getenv("REMOTE_DB_USER", "gilbot"),
            "password": os.getenv("REMOTE_DB_PASSWORD", "robot123"),
            "database": os.getenv("REMOTE_DB_NAME", "gilbot")
        }
    else:  # default to local
        config = {
            "host": os.getenv("LOCAL_DB_HOST", "localhost"),
            "port": int(os.getenv("LOCAL_DB_PORT", 3306)),
            "user": os.getenv("LOCAL_DB_USER", "gilbot"),
            "password": os.getenv("LOCAL_DB_PASSWORD", "robot123"),
            "database": os.getenv("LOCAL_DB_NAME", "gilbot")
        }
        
    try:
        connection = mysql.connector.connect(
            **config,
            charset="utf8mb4"
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL ({db_mode}): {e}")
        return None

@app.get("/")
async def root():
    db_mode = os.getenv("DB_MODE", "local").lower()
    return {
        "message": "Welcome to Gilbot API Server",
        "docs": "/docs",
        "db_mode": db_mode,
        "db_host": os.getenv(f"{db_mode.upper()}_DB_HOST")
    }

class PoseUpdate(BaseModel):
    odom_x: float
    odom_y: float

@app.post("/robot/pose")
async def update_robot_pose(pose: PoseUpdate):
    # 인메모리 업데이트 (하트비트)
    global_robot_status.last_heartbeat = datetime.now()
    global_robot_status.last_x = pose.odom_x
    global_robot_status.last_y = pose.odom_y

    conn = get_db_connection()
    if not conn:
        return {"status": "success (memory only)"}
    try:
        cursor = conn.cursor()
        # 진행 중이거나 가장 최근인 순찰 로그의 좌표 업데이트
        cursor.execute("""
            UPDATE patrol_log 
            SET last_odom_x = %s, last_odom_y = %s 
            WHERE status = '진행중' OR status = '중단'
            ORDER BY patrol_id DESC LIMIT 1
        """, (pose.odom_x, pose.odom_y))
        
        # robot_status 테이블이 있다면 시도 (오류 무시)
        try:
            cursor.execute("""
                UPDATE robot_status 
                SET last_heartbeat = CURRENT_TIMESTAMP, last_x = %s, last_y = %s 
                WHERE id = 1
            """)
        except:
            pass

        conn.commit()
        return {"status": "success"}
    except Exception as e:
        # DB 업데이트 실패해도 하트비트는 메모리에 남으므로 200 반환
        return {"status": "partial success", "detail": str(e)}
    finally:
        conn.close()

@app.get("/status")
async def get_status():
    conn = get_db_connection()
    db_status = "connected" if conn and conn.is_connected() else "disconnected"
    
    # 기본값 설정
    robot_online_status = "offline" 
    res_status = "휴식중"
    res_cmd = "None"
    res_x = global_robot_status.last_x
    res_y = global_robot_status.last_y
    
    # 1. 하트비트 체크
    if global_robot_status.last_heartbeat:
        diff = (datetime.now() - global_robot_status.last_heartbeat).total_seconds()
        if diff <= 15: # 15초 내에 통신 있으면 온라인
            robot_online_status = "online"

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # 최신 명령 확인
            cursor.execute("""
                SELECT command_type, command_id FROM robot_command 
                WHERE command_type IN ('EMERGENCY_STOP', 'RESUME_PATROL', 'RETURN_TO_BASE', 'START_PATROL')
                ORDER BY command_id DESC LIMIT 1
            """)
            mode_cmd_row = cursor.fetchone()
            mode_cmd = str(mode_cmd_row['command_type']).upper().strip() if mode_cmd_row else "NONE"
            
            # 최신 순찰 로그 확인
            cursor.execute("""
                SELECT status, last_odom_x, last_odom_y 
                FROM patrol_log ORDER BY patrol_id DESC LIMIT 1
            """)
            last_patrol = cursor.fetchone()
            p_status = str(last_patrol['status']).strip() if last_patrol else "완료"

            # 비상 여부 판정
            if "EMERGENCY" in mode_cmd or p_status == "중단":
                res_status = "비상정지"
            elif "진행" in p_status or "START" in mode_cmd:
                res_status = "순찰중"
            elif "RETURN" in mode_cmd and p_status != "완료":
                res_status = "복귀중"
            else:
                res_status = "휴식중"

            # UI 표시용 최신 명령
            cursor.execute("SELECT command_type FROM robot_command ORDER BY command_id DESC LIMIT 1")
            actual_latest = cursor.fetchone()
            res_cmd = str(actual_latest['command_type']).strip() if actual_latest else "None"

        except Exception as e:
            print(f"Status Parse Error: {e}")
        finally:
            conn.close()

    db_mode = os.getenv("DB_MODE", "local").lower()
    actual_db_host = os.getenv(f"{db_mode.upper()}_DB_HOST", "localhost")

    return {
        "status": robot_online_status,
        "robot_status": res_status,
        "latest_cmd": res_cmd,
        "database": db_status,
        "odom_x": round(res_x, 2),
        "odom_y": round(res_y, 2),
        "db_host": actual_db_host,
        "server_time": datetime.now().strftime("%H:%M:%S")
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
        cursor.execute("DELETE FROM alert WHERE patrol_id = %s", (patrol_id,))
        cursor.execute("DELETE FROM detection_log WHERE patrol_id = %s", (patrol_id,))
        cursor.execute("DELETE FROM patrol_log WHERE patrol_id = %s", (patrol_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Log not found")
        return {"message": "Patrol log and related data deleted successfully"}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.post("/patrol/start")
async def start_patrol():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("DELETE FROM detection_log")
        cursor.execute("INSERT INTO patrol_log (start_time, status) VALUES (NOW(), '진행중')")
        patrol_id = cursor.lastrowid
        cursor.execute("INSERT INTO robot_command (command_type, status) VALUES ('START_PATROL', 'PENDING')")
        conn.commit()
        return {"message": "Patrol started successfully", "patrol_id": patrol_id}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.post("/patrol/finish")
async def finish_patrol():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT patrol_id FROM patrol_log WHERE status IN ('진행중', '중단') ORDER BY start_time DESC LIMIT 1")
        patrol = cursor.fetchone()
        if patrol:
            cursor.execute(
                "UPDATE patrol_log SET status = '완료', end_time = NOW() WHERE patrol_id = %s",
                (patrol['patrol_id'],)
            )
        cursor.execute("INSERT INTO robot_command (command_type, status) VALUES ('RETURN_TO_BASE', 'PENDING')")
        conn.commit()
        return {"message": "Return to base command sent"}
    finally:
        conn.close()

@app.post("/patrol/stop")
async def stop_patrol():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("INSERT INTO robot_command (command_type, status) VALUES ('EMERGENCY_STOP', 'PENDING')")
        cursor.execute("""
            UPDATE patrol_log SET status = '중단', end_time = NOW() 
            WHERE status = '진행중' ORDER BY start_time DESC LIMIT 1
        """)
        conn.commit()
        return {"message": "Emergency stop command sent"}
    finally:
        conn.close()

@app.get("/robot/command/latest")
async def get_latest_command():
    conn = get_db_connection()
    if not conn: return {"command_type": "IDLE"}
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM robot_command WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT 1")
        cmd = cursor.fetchone()
        if cmd:
            cursor.execute("UPDATE robot_command SET status = 'PROCESSING' WHERE command_id = %s", (cmd['command_id'],))
            conn.commit()
            return cmd
        return {"command_type": "IDLE"}
    finally:
        conn.close()

@app.post("/robot/command/{command_id}/complete")
async def complete_command(command_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE robot_command SET status = 'COMPLETED' WHERE command_id = %s", (command_id,))
        conn.commit()
        return {"message": "Success"}
    finally:
        conn.close()

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
        query = "INSERT INTO product_master (product_name, barcode, category, min_inventory_qty, yolo_class_id) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(query, (product.product_name, product.barcode, product.category, product.min_inventory_qty, product.yolo_class_id))
        conn.commit()
        return {"message": "Product added successfully", "id": cursor.lastrowid}
    finally:
        conn.close()

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

@app.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE alert SET is_resolved = TRUE WHERE alert_id = %s", (alert_id,))
        conn.commit()
        return {"message": "Alert marked as resolved"}
    finally:
        conn.close()

@app.post("/detections/add")
async def add_detection(data: DetectionInput):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT patrol_id FROM patrol_log WHERE status = '진행중' ORDER BY start_time DESC LIMIT 1")
        patrol = cursor.fetchone()
        patrol_id = patrol['patrol_id'] if patrol else 0

        cursor.execute("SELECT waypoint_id, product_id, row_num FROM waypoint_product_plan WHERE barcode_tag = %s", (data.tag_barcode,))
        plan = cursor.fetchone()
        if not plan: return {"status": "error", "message": "tag not found"}

        cursor.execute("SELECT product_id FROM product_master WHERE barcode = %s", (data.detected_barcode,))
        prod = cursor.fetchone()
        detected_id = prod['product_id'] if prod else None

        result_status = '정상'
        if not data.detected_barcode: result_status = '결품'
        elif detected_id != plan['product_id']: result_status = '오진열'

        cursor.execute("""
            INSERT INTO detection_log (patrol_id, waypoint_id, product_id, detected_product_id, detected_barcode, tag_barcode, confidence, result, odom_x, odom_y)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (patrol_id, plan['waypoint_id'], plan['product_id'], detected_id, data.detected_barcode, data.tag_barcode, data.confidence, result_status, data.odom_x, data.odom_y))

        if result_status != '정상' and patrol_id > 0:
            cursor.execute("""
                INSERT INTO alert (patrol_id, waypoint_id, barcode_tag, product_id, alert_type, message)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (patrol_id, plan['waypoint_id'], data.tag_barcode, plan['product_id'], result_status, result_status))

        conn.commit()
        return {"status": "success", "judgment": result_status}
    finally:
        conn.close()

@app.get("/detections")
async def list_detections():
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT patrol_id FROM patrol_log ORDER BY patrol_id DESC LIMIT 1")
        res = cursor.fetchone()
        if not res: return []
        cursor.execute("""
            SELECT d.*, p1.product_name as p_name_target, p2.product_name as p_name_detected
            FROM detection_log d
            LEFT JOIN product_master p1 ON d.product_id = p1.product_id
            LEFT JOIN product_master p2 ON d.detected_product_id = p2.product_id
            WHERE d.patrol_id = %s ORDER BY d.log_id ASC
        """, (res['patrol_id'],))
        return cursor.fetchall()
    finally:
        conn.close()

@app.get("/patrol/config")
async def get_patrol_config():
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM patrol_config ORDER BY config_id DESC LIMIT 1")
        config = cursor.fetchone()
        return config or {"avoidance_wait_time": 10, "is_active": True}
    finally:
        if conn: conn.close()

@app.post("/patrol/config")
async def update_patrol_config(config: PatrolConfig):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO patrol_config (avoidance_wait_time, patrol_start_time, patrol_end_time, interval_hour, interval_minute, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (config.avoidance_wait_time, config.patrol_start_time, config.patrol_end_time, config.interval_hour, config.interval_minute, config.is_active))
        conn.commit()
        return {"message": "Success"}
    finally:
        conn.close()

@app.get("/patrol/plan")
async def get_patrol_plan():
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*, w.waypoint_name, m.product_name, m.barcode as product_barcode
            FROM waypoint_product_plan p
            LEFT JOIN waypoint w ON p.waypoint_id = w.waypoint_id
            LEFT JOIN product_master m ON p.product_id = m.product_id
            ORDER BY p.plan_order, p.plan_id
        """)
        return cursor.fetchall()
    finally:
        if conn: conn.close()

@app.get("/waypoints")
async def list_waypoints():
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM waypoint ORDER BY waypoint_id")
        return cursor.fetchall()
    finally:
        if conn: conn.close()

@app.put("/waypoints/{waypoint_id}")
async def update_waypoint(waypoint_id: int, wp: WaypointUpdate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE waypoint SET waypoint_no = %s, waypoint_name = %s, loc_x = %s, loc_y = %s WHERE waypoint_id = %s
        """, (wp.waypoint_no, wp.waypoint_name, wp.loc_x, wp.loc_y, waypoint_id))
        conn.commit()
        return {"message": "Success"}
    finally:
        conn.close()

@app.delete("/waypoints/{waypoint_id}")
async def delete_waypoint(waypoint_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM waypoint_product_plan WHERE waypoint_id = %s", (waypoint_id,))
        cursor.execute("DELETE FROM shelf_status WHERE waypoint_id = %s", (waypoint_id,))
        cursor.execute("DELETE FROM waypoint WHERE waypoint_id = %s", (waypoint_id,))
        conn.commit()
        return {"message": "Success"}
    finally:
        conn.close()

@app.post("/admin/unified-register")
async def unified_register(data: UnifiedRegisterInput):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT product_id FROM product_master WHERE barcode = %s", (data.product_barcode,))
        prod = cursor.fetchone()
        if prod:
            product_id = prod['product_id']
            cursor.execute("UPDATE product_master SET product_name = %s, category = %s, min_inventory_qty = %s, yolo_class_id = %s WHERE product_id = %s", (data.product_name, data.category, data.min_inventory_qty, data.yolo_class_id, product_id))
        else:
            cursor.execute("INSERT INTO product_master (product_name, barcode, category, min_inventory_qty, yolo_class_id) VALUES (%s, %s, %s, %s, %s)", (data.product_name, data.product_barcode, data.category, data.min_inventory_qty, data.yolo_class_id))
            product_id = cursor.lastrowid

        cursor.execute("SELECT waypoint_id FROM waypoint WHERE waypoint_name = %s", (data.waypoint_name,))
        wp = cursor.fetchone()
        if wp: waypoint_id = wp['waypoint_id']
        else:
            cursor.execute("INSERT INTO waypoint (waypoint_no, waypoint_name, loc_x, loc_y) VALUES (100, %s, 0.0, 0.0)", (data.waypoint_name,))
            waypoint_id = cursor.lastrowid

        cursor.execute("SELECT plan_id FROM waypoint_product_plan WHERE barcode_tag = %s", (data.product_barcode,))
        p = cursor.fetchone()
        if p: cursor.execute("UPDATE waypoint_product_plan SET product_id = %s, waypoint_id = %s, row_num = %s WHERE plan_id = %s", (product_id, waypoint_id, data.row_num, p['plan_id']))
        else: cursor.execute("INSERT INTO waypoint_product_plan (waypoint_id, product_id, barcode_tag, row_num) VALUES (%s, %s, %s, %s)", (waypoint_id, product_id, data.product_barcode, data.row_num))

        conn.commit()
        return {"message": "Success"}
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
