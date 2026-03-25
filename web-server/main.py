from fastapi import FastAPI

app = FastAPI(
    title="Gilbot API Server",
    description="편의점 매대 관리 로봇(Gilbot) 제어를 위한 백엔드 서버",
    version="0.1.0"
)

@app.get("/")
async def root():
    return {
        "message": "Welcome to Gilbot API Server",
        "docs": "/docs"
    }

@app.get("/status")
async def get_status():
    # 추후 DB 연결 확인 로직 추가 예정
    return {
        "status": "running",
        "database": "disconnected"
    }

@app.get("/patrol/list")
async def list_patrols():
    # 순찰 기록 조회 예시
    return []

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
