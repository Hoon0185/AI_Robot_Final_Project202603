import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

# 환경 변수 로드 (.env 파일이 있으면 읽어옴)
load_dotenv()

app = FastAPI(
    title="Gilbot API Server",
    description="편의점 매대 관리 로봇(Gilbot) 제어를 위한 백엔드 서버",
    version="0.2.2"
)

# CORS 설정: 프론트엔드(React 등)의 접속을 허용합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실무에서는 ["http://localhost:3000"] 처럼 특정 주소만 넣는 것을 권장합니다.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

if __name__ == "__main__":
    import uvicorn
    # 외부 IP 허용 및 포트 8000 실행
    uvicorn.run(app, host="0.0.0.0", port=8000)
