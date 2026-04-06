import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, APIRouter
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
    version="0.3.0"
)

# API 라우터 설정 (기본 /api 경로 사용)
router = APIRouter(prefix="/api")

# CORS 설정: 프론트엔드(React 등)의 접속을 허용합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HMI 정적 파일 서빙 설정 (루트 /hmi 경로로 직접 제공)
from fastapi.staticfiles import StaticFiles
app.mount("/hmi", StaticFiles(directory="hmi", html=True), name="hmi")

# 전역 상태 (메모리 상에 유지, 시스템 재시작 시 초기화)
current_robot_alert = {
    "message": None,
    "active": False,
    "timestamp": None
}

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

@router.get("/")
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

@router.post("/robot/pose")
async def update_robot_pose(pose: PoseUpdate):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        # 진행 중이거나 가장 최근인 순찰 로그의 좌표 업데이트
        cursor.execute("""
            UPDATE patrol_log 
            SET last_odom_x = %s, last_odom_y = %s 
            WHERE status = '진행중' OR status = '중단'
            ORDER BY patrol_id DESC LIMIT 1
        """, (pose.odom_x, pose.odom_y))
        
        # 하트비트 테이블 및 최신 좌표 갱신 추가
        cursor.execute("""
            UPDATE robot_status 
            SET last_heartbeat = CURRENT_TIMESTAMP, 
                last_x = %s, 
                last_y = %s 
            WHERE id = 1
        """, (pose.odom_x, pose.odom_y))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@router.get("/status")
async def get_status():
    conn = get_db_connection()
    db_status = "connected" if conn and conn.is_connected() else "disconnected"
    
    # 기본값 설정
    robot_online_status = "offline" # 로봇 통신 상태 (online/offline)
    res_status = "휴식중"
    res_cmd = "None"
    res_x = 0.0
    res_y = 0.0
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # 1. 최신 '모드 정의' 명령 확인 (ID 기준 정렬로 클럭 드리프트 문제 방지)
            cursor.execute("""
                SELECT command_type, command_id FROM robot_command 
                WHERE command_type IN ('EMERGENCY_STOP', 'RESUME_PATROL', 'RETURN_TO_BASE', 'START_PATROL')
                ORDER BY command_id DESC LIMIT 1
            """)
            mode_cmd_row = cursor.fetchone()
            mode_cmd = str(mode_cmd_row['command_type']).upper().strip() if mode_cmd_row else "NONE"
            mode_cmd_id = mode_cmd_row['command_id'] if mode_cmd_row else 0
            
            # --- 하트비트 기반 온라인/오프라인 판정 및 최신 좌표 추출 ---
            # (Chrony 동기화가 완료되어 이제 시차가 매우 정확함)
            cursor.execute("SELECT last_heartbeat, last_x, last_y FROM robot_status WHERE id = 1")
            hb_row = cursor.fetchone()
            if hb_row:
                last_hb = hb_row['last_heartbeat']
                res_x = round(hb_row['last_x'] or 0.0, 2)
                res_y = round(hb_row['last_y'] or 0.0, 2)
                
                # 시차 계산 (현재 시각 - 마지막 하트비트)
                diff = (datetime.now() - last_hb).total_seconds()
                if diff <= 5: # 기존 10초에서 5초로 단축하여 반응성 향상
                    robot_online_status = "online"
                else:
                    robot_online_status = "offline"
            # ---------------------------------------
            
            # 2. 최신 순찰 로그 확인
            cursor.execute("SELECT status, last_odom_x, last_odom_y FROM patrol_log ORDER BY patrol_id DESC LIMIT 1")
            last_patrol = cursor.fetchone()
            p_status = str(last_patrol['status']).strip() if last_patrol else "완료"

            # 3. 비상 여부 판론 (최우선: 명령이 EMERGENCY거나 로그가 중단인 경우)
            if "EMERGENCY" in mode_cmd or p_status == "중단":
                res_status = "비상정지"
                # 비상정지 시에도 진행 중이었다면 마지막 좌표를 유지, 아니면 (기지 복귀 완료 시 등) 0,0
                if p_status != "완료" and last_patrol:
                    res_x = round(last_patrol.get('last_odom_x', 0.0), 2)
                    res_y = round(last_patrol.get('last_odom_y', 0.0), 2)
            elif "진행" in p_status or "START" in mode_cmd:
                res_status = "순찰중"
                if last_patrol:
                    res_x = round(last_patrol.get('last_odom_x', 0.0), 2)
                    res_y = round(last_patrol.get('last_odom_y', 0.0), 2)
            elif "RETURN" in mode_cmd and p_status != "완료":
                res_status = "순찰중" # 복귀 중도 순찰중으로 표시 (또는 '복귀중' 추가 가능)
                if last_patrol:
                    res_x = round(last_patrol.get('last_odom_x', 0.0), 2)
                    res_y = round(last_patrol.get('last_odom_y', 0.0), 2)
            else:
                res_status = "휴식중"
                # 휴식 중에도 로봇이 전송한 최신 좌표를 유지 (위에서 hb_row로 이미 설정됨)

            # 최종 응답용 최신 명령 (UI 표시용)
            cursor.execute("SELECT command_type FROM robot_command ORDER BY command_id DESC LIMIT 1")
            actual_latest = cursor.fetchone()
            res_cmd = str(actual_latest['command_type']).strip() if actual_latest else "None"

            # 디버깅용 로그 출력
            db_mode = os.getenv("DB_MODE", "local").lower()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] STATUS CHECK: mode_cmd={mode_cmd}(ID:{mode_cmd_id}), patrol_status={p_status}, db_mode={db_mode}")

        except Exception as e:
            # 에러 로그는 서버 측에만 남기고 판정은 기본값(휴식중) 유지
            print(f"Status Parse Error: {e}")
        finally:
            conn.close()

    # 실제 접속된 DB 호스트 확인 (환경 변수 또는 기본값)
    db_mode = os.getenv("DB_MODE", "local").lower()
    actual_db_host = os.getenv(f"{db_mode.upper()}_DB_HOST", "localhost")

    return {
        "status": robot_online_status,
        "robot_status": res_status,
        "latest_cmd": res_cmd,
        "database": db_status,
        "odom_x": res_x,
        "odom_y": res_y,
        "db_host": actual_db_host,
        "server_time": datetime.now().strftime("%H:%M:%S")
    }

@router.get("/patrol/list")
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

@router.post("/patrol/add")
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

@router.delete("/patrol/{patrol_id}")
async def delete_patrol(patrol_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # 1. 관련된 alert 삭제
        cursor.execute("DELETE FROM alert WHERE patrol_id = %s", (patrol_id,))
        # 2. 관련된 detection_log 삭제
        cursor.execute("DELETE FROM detection_log WHERE patrol_id = %s", (patrol_id,))
        # 3. 순찰 로그 삭제
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

@router.post("/patrol/start")
async def start_patrol():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 비상정지 상태 확인
        cursor.execute("""
            SELECT command_type FROM robot_command 
            WHERE command_type IN ('EMERGENCY_STOP', 'RESUME_PATROL', 'RETURN_TO_BASE', 'START_PATROL')
            ORDER BY created_at DESC, command_id DESC LIMIT 1
        """)
        last_cmd = cursor.fetchone()
        cursor.execute("SELECT status FROM patrol_log ORDER BY patrol_id DESC LIMIT 1")
        last_patrol = cursor.fetchone()
        
        is_locked = (last_patrol and last_patrol['status'] == '중단') or (last_cmd and last_cmd['command_type'] == 'EMERGENCY_STOP')
        
        if is_locked:
            raise HTTPException(status_code=403, detail="비상정지 상태입니다. 비상해제를 먼저 눌러주세요.")

        # 0. 기존 인식 로그 초기화 (새 순찰 시작 시 클리어 요청 반영)
        cursor.execute("DELETE FROM detection_log")

        # 1. 새로운 순찰 로그 생성
        cursor.execute("INSERT INTO patrol_log (start_time, status) VALUES (NOW(), '진행중')")

        patrol_id = cursor.lastrowid
        
        # 2. 로봇 명령 큐에 추가
        cursor.execute("INSERT INTO robot_command (command_type, status) VALUES ('START_PATROL', 'PENDING')")
        
        conn.commit()
        return {"message": "Patrol started successfully", "patrol_id": patrol_id}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@router.post("/patrol/finish")
async def finish_patrol():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 비상정지 상태 상관없이 복귀 명령을 내리면 해제 효과를 가지도록 수정 (사용자 요청: 비상정지 중 복귀 누르면 해제)
        # 이전 제약 조건 제거

        # '진행중' 또는 '중단' 상태인 최신 순찰을 찾음
        cursor.execute("SELECT patrol_id FROM patrol_log WHERE status IN ('진행중', '중단') ORDER BY start_time DESC LIMIT 1")

        patrol = cursor.fetchone()
        
        if patrol:
            patrol_id = patrol['patrol_id']
            cursor.execute(
                "UPDATE patrol_log SET status = '완료', end_time = NOW() WHERE patrol_id = %s",
                (patrol_id,)
            )
        
        # 로봇 명령 큐에 복귀 추가 (비상 정지 상태였을 경우에도 해제 효과를 가짐)
        cursor.execute("INSERT INTO robot_command (command_type, status) VALUES ('RETURN_TO_BASE', 'PENDING')")
        
        conn.commit()
        return {"message": "Return to base command sent", "patrol_id": patrol['patrol_id'] if patrol else None}
    finally:
        conn.close()


@router.post("/patrol/stop")
async def stop_patrol():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        # 1. 일단 로봇 명령 큐에 비상정지 추가 (최우선)
        cursor.execute("INSERT INTO robot_command (command_type, status) VALUES ('EMERGENCY_STOP', 'PENDING')")
        
        # 2. 진행중인 순찰이 있다면 '중단'으로 변경
        cursor.execute("SELECT patrol_id FROM patrol_log WHERE status = '진행중' ORDER BY start_time DESC LIMIT 1")
        patrol = cursor.fetchone()
        patrol_id = None
        if patrol:
            patrol_id = patrol['patrol_id']
            cursor.execute(
                "UPDATE patrol_log SET status = '중단', end_time = NOW() WHERE patrol_id = %s",
                (patrol_id,)
            )
        
        conn.commit()
        return {"message": "Emergency stop command sent", "patrol_id": patrol_id}
    finally:
        conn.close()

@router.post("/patrol/resume")
async def resume_patrol():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        # 마지막 중단된 순찰 회차 조회
        cursor.execute("SELECT patrol_id FROM patrol_log WHERE status = '중단' ORDER BY patrol_id DESC LIMIT 1")
        patrol = cursor.fetchone()
        
        if patrol:
            patrol_id = patrol['patrol_id']
            # 상태를 다시 '진행중'으로 복구
            cursor.execute(
                "UPDATE patrol_log SET status = '진행중', end_time = NULL WHERE patrol_id = %s",
                (patrol_id,)
            )
        
        # 기지에 정지상태이든 순찰중이었든 상관없이 비상정지 신호 해제를 위해 명령 전송
        cursor.execute("INSERT INTO robot_command (command_type, status) VALUES ('RESUME_PATROL', 'PENDING')")
        
        conn.commit()
        return {"message": "Patrol resume/Emergency release command sent", "patrol_id": patrol['patrol_id'] if patrol else None}
    finally:
        conn.close()



@router.get("/robot/command/latest")
async def get_latest_command():
    conn = get_db_connection()
    if not conn: return {"command": "IDLE"}
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM robot_command WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT 1")
        cmd = cursor.fetchone()
        if cmd:
            # 처리 중으로 변경
            cursor.execute("UPDATE robot_command SET status = 'PROCESSING' WHERE command_id = %s", (cmd['command_id'],))
            conn.commit()
            return cmd
        return {"command_type": "IDLE"}
    finally:
        conn.close()

@router.post("/robot/command/clear_pending")
async def clear_pending_commands():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        # 1. 미완료된 로봇 명령 초기화 (DB Enum에 맞춰 FAILED로 변경)
        cursor.execute("UPDATE robot_command SET status = 'FAILED' WHERE status IN ('PENDING', 'PROCESSING')")
        cmd_count = cursor.rowcount
        
        # 2. '진행중'인 순찰 로그 모두 강제 중단 처리 (잔류 로그 정리)
        cursor.execute("UPDATE patrol_log SET status = '중단', end_time = NOW() WHERE status = '진행중'")
        log_count = cursor.rowcount
        
        conn.commit()
        print(f"🧹 CLEAR: {cmd_count} commands and {log_count} patrol logs cleared.")
        return {
            "message": "All pending commands and stale patrol logs cleared",
            "commands_cleared_count": cmd_count,
            "patrol_logs_cleared_count": log_count
        }
    finally:
        conn.close()

@router.post("/robot/command/{command_id}/complete")
async def complete_command(command_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE robot_command SET status = 'COMPLETED' WHERE command_id = %s", (command_id,))
        conn.commit()
        return {"message": "Success"}
    finally:
        conn.close()

# --- Product Master Admin API ---

@router.get("/products")
async def list_products():
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM product_master ORDER BY product_id DESC")
        return cursor.fetchall()
    finally:
        conn.close()

@router.post("/products/add")
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

@router.put("/products/{product_id}/inventory")
async def update_inventory(product_id: int, data: InventoryUpdate):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        # Check current min inventory qty
        cursor.execute("SELECT min_inventory_qty FROM product_master WHERE product_id = %s", (product_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        
        min_qty = row['min_inventory_qty']
        alert_log = "재고 부족 (최소 유지 수량 미달)" if data.current_inventory_qty < min_qty else None
        is_alert_resolved = False if data.current_inventory_qty < min_qty else True
        
        query = """
            UPDATE product_master 
            SET current_inventory_qty = %s, alert_log = %s, is_alert_resolved = %s
            WHERE product_id = %s
        """
        cursor.execute(query, (data.current_inventory_qty, alert_log, is_alert_resolved, product_id))
        conn.commit()
        return {"message": "Inventory updated successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@router.put("/products/{product_id}/resolve_alert")
async def resolve_inventory_alert(product_id: int):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE product_master SET is_alert_resolved = TRUE WHERE product_id = %s", (product_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"message": "Inventory alert resolved successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# --- Analysis & Detection API ---

@router.get("/alerts")
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

@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE alert SET is_resolved = TRUE WHERE alert_id = %s", (alert_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"message": "Alert marked as resolved"}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@router.post("/detections/add")
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
            # 진행 중인 순찰이 없으면 자동으로 새 순찰 회차 시작
            cursor.execute("INSERT INTO patrol_log (start_time, status) VALUES (NOW(), '진행중')")
            conn.commit()
            patrol_id = cursor.lastrowid
        else:
            patrol_id = patrol['patrol_id']

        # 2. 태그 바코드로 해당 위치 및 계획된 상품 조회
        query_plan = """
            SELECT plan_id, waypoint_id, product_id as planned_product_id, row_num
            FROM waypoint_product_plan
            WHERE barcode_tag = %s
        """
        cursor.execute(query_plan, (data.tag_barcode,))
        plan = cursor.fetchone()
        
        if not plan:
             raise HTTPException(status_code=404, detail=f"Tag barcode {data.tag_barcode} not found in plan")
        
        waypoint_id = plan['waypoint_id']
        planned_product_id = plan['planned_product_id']
        row_num = plan['row_num']

        # 3. 인식된 바코드 또는 YOLO ID로 실제 바코드 및 상품 정보 조회
        final_detected_barcode = data.detected_barcode
        detected_product_id_internal = None # 판독용 내부 변수
        
        if not final_detected_barcode and data.yolo_class_id is not None and data.yolo_class_id not in [-1, 0]:
            # YOLO 클래스 아이디로 상품 바코드 조회
            cursor.execute("SELECT barcode, product_id FROM product_master WHERE yolo_class_id = %s", (data.yolo_class_id,))
            prod = cursor.fetchone()
            if prod:
                final_detected_barcode = prod['barcode']
                detected_product_id_internal = prod['product_id']
        elif final_detected_barcode:
            # 바코드가 직접 들어온 경우 내부 검증용 ID 조회
            cursor.execute("SELECT product_id FROM product_master WHERE barcode = %s", (final_detected_barcode,))
            prod = cursor.fetchone()
            if prod:
                detected_product_id_internal = prod['product_id']

        # 4. 판독 로직 (정상 / 결품 / 오진열)
        result_status = '정상'
        if not final_detected_barcode and (data.yolo_class_id is None or data.yolo_class_id in [-1, 0]):
            result_status = '결품'
        elif detected_product_id_internal != planned_product_id:
            result_status = '오진열'

        # 5. shelf_status 업데이트 (현재 매대 현황)
        cursor.execute("SELECT status_id FROM shelf_status WHERE barcode_tag = %s", (data.tag_barcode,))
        existing_status = cursor.fetchone()
        
        if existing_status:
            update_status_sql = "UPDATE shelf_status SET product_id = %s, status = %s, last_updated_at = NOW() WHERE barcode_tag = %s"
            cursor.execute(update_status_sql, (detected_product_id_internal or planned_product_id, result_status, data.tag_barcode))
        else:
            insert_status_sql = "INSERT INTO shelf_status (waypoint_id, barcode_tag, product_id, status) VALUES (%s, %s, %s, %s)"
            cursor.execute(insert_status_sql, (waypoint_id, data.tag_barcode, detected_product_id_internal or planned_product_id, result_status))

        # 6. detection_log (인식 이력 기록)
        insert_log_sql = """
            INSERT INTO detection_log (patrol_id, waypoint_id, product_id, detected_barcode, tag_barcode, confidence, result, odom_x, odom_y)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_log_sql, (patrol_id, waypoint_id, planned_product_id, final_detected_barcode, data.tag_barcode, data.confidence, result_status, data.odom_x, data.odom_y))

        # 7. Alert 생성 (이상 감제 시)
        if result_status != '정상':
            alert_msg = f"{data.tag_barcode} 위치: 계획된 상품과 다름" if result_status == '오진열' else f"{data.tag_barcode} 위치: 결품"
            insert_alert_sql = """
                INSERT INTO alert (patrol_id, waypoint_id, barcode_tag, product_id, alert_type, message)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_alert_sql, (patrol_id, waypoint_id, data.tag_barcode, planned_product_id, result_status, alert_msg))

        # 8. patrol_log 통계 업데이트
        update_patrol_sql = "UPDATE patrol_log SET scanned_slots = scanned_slots + 1, error_found = error_found + %s WHERE patrol_id = %s"
        cursor.execute(update_patrol_sql, (1 if result_status != '정상' else 0, patrol_id))

        conn.commit()
        return {
            "status": "success", 
            "judgment": result_status, 
            "location": f"Waypoint {waypoint_id}, Row {row_num}",
            "tag_barcode": data.tag_barcode,
            "patrol_id": patrol_id
        }

    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@router.get("/detections")
async def list_detections():
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        # 가장 최근의 순찰 ID를 가져옴 (진행중이거나 완료된 것 모두)
        cursor.execute("SELECT patrol_id FROM patrol_log ORDER BY patrol_id DESC LIMIT 1")
        latest_patrol = cursor.fetchone()
        
        if not latest_patrol:
            return []
            
        active_id = latest_patrol['patrol_id']
        query = """
            SELECT d.*, 
                   p1.product_name as p_name_target,
                   p2.product_name as p_name_detected
            FROM detection_log d
            LEFT JOIN product_master p1 ON d.product_id = p1.product_id
            LEFT JOIN product_master p2 ON d.detected_barcode = p2.barcode
            WHERE d.patrol_id = %s
            ORDER BY d.log_id ASC
        """
        cursor.execute(query, (active_id,))
        return cursor.fetchall()
    finally:
        conn.close()

# --- Config & Plan API ---

@router.get("/patrol/config")
async def get_patrol_config():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
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
            return {
                "avoidance_wait_time": 10,
                "patrol_start_time": "09:00:00",
                "patrol_end_time": "22:00:00",
                "interval_hour": 1,
                "interval_minute": 0,
                "is_active": True
            }
        return config
    finally:
        conn.close()

@router.post("/patrol/config")
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

@router.get("/patrol/plan")
async def get_patrol_plan():
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                p.plan_id, p.waypoint_id, p.barcode_tag, p.product_id,
                p.plan_order, w.waypoint_name, w.loc_x, w.loc_y, p.row_num,
                m.product_name, m.barcode as product_barcode
            FROM waypoint_product_plan p
            LEFT JOIN waypoint w ON p.waypoint_id = w.waypoint_id
            LEFT JOIN product_master m ON p.product_id = m.product_id
            ORDER BY p.plan_order, p.plan_id
        """
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        conn.close()

@router.post("/patrol/plan/add")
async def add_patrol_plan(plan: PlanAddInput):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT plan_id FROM waypoint_product_plan WHERE barcode_tag = %s", (plan.barcode_tag,))
        existing_plan = cursor.fetchone()
        
        if existing_plan:
            cursor.execute(
                "UPDATE waypoint_product_plan SET product_id = %s, waypoint_id = %s, row_num = %s WHERE plan_id = %s",
                (plan.product_id, plan.waypoint_id, plan.row_num, existing_plan['plan_id'])
            )
        else:
            cursor.execute(
                "INSERT INTO waypoint_product_plan (waypoint_id, barcode_tag, product_id, row_num) VALUES (%s, %s, %s, %s)",
                (plan.waypoint_id, plan.barcode_tag, plan.product_id, plan.row_num)
            )
        
        conn.commit()
        return {"message": "Planogram updated successfully"}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# --- Inventory & Admin API ---

@router.get("/inventory")
async def list_inventory():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                ss.*, 
                p.product_name, 
                p.barcode AS product_barcode,
                w.waypoint_name,
                pp.row_num,
                mp.product_name AS planned_product_name,
                mp.barcode AS planned_product_barcode
            FROM shelf_status ss
            LEFT JOIN product_master p ON ss.product_id = p.product_id
            LEFT JOIN waypoint w ON ss.waypoint_id = w.waypoint_id
            LEFT JOIN waypoint_product_plan pp ON ss.barcode_tag = pp.barcode_tag
            LEFT JOIN product_master mp ON pp.product_id = mp.product_id
            ORDER BY ss.last_updated_at DESC
        """
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        conn.close()

@router.post("/patrol/plan/order")
async def update_patrol_plan_order(orders: List[PlanOrderUpdate]):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        for item in orders:
            cursor.execute(
                "UPDATE waypoint_product_plan SET plan_order = %s WHERE plan_id = %s",
                (item.plan_order, item.plan_id)
            )
        conn.commit()
        return {"message": "Patrol sequences optimized successfully"}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@router.delete("/patrol/plan/{plan_id}")
async def delete_patrol_plan(plan_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM waypoint_product_plan WHERE plan_id = %s", (plan_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Plan not found")
        return {"message": "Planogram record removed successfully"}
    finally:
        conn.close()

@router.post("/waypoints/order")
async def update_waypoints_order(orders: List[WaypointOrderUpdate]):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        for item in orders:
            cursor.execute(
                "UPDATE waypoint SET visit_order = %s WHERE waypoint_id = %s",
                (item.visit_order, item.waypoint_id)
            )
        conn.commit()
        return {"message": "Waypoint orders updated successfully"}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@router.put("/waypoints/{waypoint_id}")
async def update_waypoint(waypoint_id: int, wp: WaypointUpdate):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB Connection Error")
    try:
        cursor = conn.cursor()
        query = """
            UPDATE waypoint 
            SET waypoint_no = %s, waypoint_name = %s, loc_x = %s, loc_y = %s 
            WHERE waypoint_id = %s
        """
        cursor.execute(query, (wp.waypoint_no, wp.waypoint_name, wp.loc_x, wp.loc_y, waypoint_id))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="웨이포인트를 찾을 수 없습니다.")
        return {"message": "웨이포인트 정보가 업데이트되었습니다."}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"DB Error: {str(e)}")
    finally:
        conn.close()

@router.get("/waypoints")
async def list_waypoints():
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM waypoint ORDER BY waypoint_id")
        return cursor.fetchall()
    finally:
        conn.close()

@router.delete("/waypoints/{waypoint_id}")
async def delete_waypoint(waypoint_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. 진열 계획 및 매대 현황 데이터 삭제 (CASCADE 수동 구현)
        cursor.execute("DELETE FROM waypoint_product_plan WHERE waypoint_id = %s", (waypoint_id,))
        cursor.execute("DELETE FROM shelf_status WHERE waypoint_id = %s", (waypoint_id,))
        
        # 2. 관련 순찰 로그 내역 및 알림 내역 삭제
        cursor.execute("DELETE FROM detection_log WHERE waypoint_id = %s", (waypoint_id,))
        cursor.execute("DELETE FROM alert WHERE waypoint_id = %s", (waypoint_id,))
        
        # 3. 웨이포인트 본체 삭제
        cursor.execute("DELETE FROM waypoint WHERE waypoint_id = %s", (waypoint_id,))
        
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="웨이포인트를 찾을 수 없습니다.")
        
        return {"message": "웨이포인트 및 관련 모든 데이터가 삭제되었습니다."}
        
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"데이터베이스 오류: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")
    finally:
        conn.close()

@router.delete("/waypoints/{waypoint_id}/clear_plans")
async def clear_waypoint_plans(waypoint_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM waypoint_product_plan WHERE waypoint_id = %s", (waypoint_id,))
        conn.commit()
        return {"message": "All product plans for this waypoint have been cleared."}
    finally:
        conn.close()

@router.post("/admin/unified-register")
async def unified_register(data: UnifiedRegisterInput):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor(dictionary=True)
        # 1. 상품 등록/업데이트
        cursor.execute("SELECT product_id FROM product_master WHERE barcode = %s", (data.product_barcode,))
        prod = cursor.fetchone()
        if prod:
            product_id = prod['product_id']
            cursor.execute(
                "UPDATE product_master SET product_name = %s, category = %s, min_inventory_qty = %s, yolo_class_id = %s WHERE product_id = %s",
                (data.product_name, data.category, data.min_inventory_qty, data.yolo_class_id, product_id)
            )
        else:
            cursor.execute(
                "INSERT INTO product_master (product_name, barcode, category, min_inventory_qty, yolo_class_id) VALUES (%s, %s, %s, %s, %s)",
                (data.product_name, data.product_barcode, data.category, data.min_inventory_qty, data.yolo_class_id)
            )
            product_id = cursor.lastrowid

        # 2. 웨이포인트 조회/생성
        cursor.execute("SELECT waypoint_id FROM waypoint WHERE waypoint_name = %s", (data.waypoint_name,))
        wp = cursor.fetchone()
        if wp:
            waypoint_id = wp['waypoint_id']
        else:
            cursor.execute("SELECT MAX(waypoint_no) as max_no FROM waypoint")
            res_max = cursor.fetchone()
            new_no = (res_max['max_no'] if res_max and res_max['max_no'] else 100) + 1
            cursor.execute(
                "INSERT INTO waypoint (waypoint_no, waypoint_name, loc_x, loc_y) VALUES (%s, %s, 0.0, 0.0)", 
                (new_no, data.waypoint_name)
            )
            waypoint_id = cursor.lastrowid

        # 3. 진열 계획 업데이트
        cursor.execute("SELECT plan_id FROM waypoint_product_plan WHERE barcode_tag = %s", (data.product_barcode,))
        p = cursor.fetchone()
        if p:
            cursor.execute(
                "UPDATE waypoint_product_plan SET product_id = %s, waypoint_id = %s, row_num = %s WHERE plan_id = %s",
                (product_id, waypoint_id, data.row_num, p['plan_id'])
            )
        else:
            cursor.execute(
                "INSERT INTO waypoint_product_plan (waypoint_id, product_id, barcode_tag, row_num) VALUES (%s, %s, %s, %s)",
                (waypoint_id, product_id, data.product_barcode, data.row_num)
            )

        conn.commit()
        return {"message": "Success", "product_id": product_id}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# --- Robot Alert 엔드포인트 (HMI 실시간 알림용) ---
@router.get("/robot/alert")
async def get_robot_alert():
    return current_robot_alert

@router.post("/robot/alert")
async def post_robot_alert(data: dict):
    # data 예시: {"message": "우회로 탐색 중...", "active": true}
    current_robot_alert["message"] = data.get("message")
    current_robot_alert["active"] = data.get("active", False)
    current_robot_alert["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {"status": "success", "alert": current_robot_alert}

@router.post("/robot/alert/clear")
async def clear_robot_alert():
    current_robot_alert["message"] = None
    current_robot_alert["active"] = False
    current_robot_alert["timestamp"] = None
    return {"status": "success"}

# API 라우터 최종 등록
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
