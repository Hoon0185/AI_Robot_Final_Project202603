# 🚀 FastAPI 도입 및 백엔드 서버 구축 가이드

> **연관 파일:** [`erd.md`](./erd.md) | [`create_tables.sql`](./create_tables.sql)  
> **프로젝트:** AI 로봇 프로그래밍 최종 팀 프로젝트 (Gilbot)  
> **작성일:** 2026-03-25  

---

## 1. 프레임워크 선정: FastAPI vs Flask

| 특징 | FastAPI | Flask |
| :--- | :--- | :--- |
| **성능** | 매우 높음 (Starlette & Pydantic 기반) | 보통 |
| **타입 힌팅** | **Native 지원** | 미지원 (수동 검증 필요) |
| **비동기(Async)** | **Native 지원** (`async`/`await`) | 2.0부터 지원 (비관적) |
| **문서화** | **Swagger UI/ReDoc 자동 생성** | 플러그인 필수 |
| **개발 속도** | 매우 빠름 | 단순하지만 생산성 낮음 |

### ✅ FastAPI를 선택한 이유
로봇(Gilbot) 프로젝트는 실시간 데이터 수급 및 센서 통신이 빈번하므로, **고성능 비동기 처리(`asyncio`)**가 강점인 FastAPI가 가장 적합합니다. 또한 개발과 동시에 생성되는 API 문서(Swagger)는 기획 및 테스트 단계에서 매우 유용합니다.

---

## 2. 설치 및 환경 구축

### 1) 패키지 설치
터미널에서 아래 명령어를 실행하여 필요한 패키지를 설치합니다.
```bash
pip install fastapi uvicorn
```

### 2) 서버 실행 방법
`web-server` 디렉토리로 이동하여 아래 명령어를 입력합니다.
```bash
# --reload 옵션은 코드가 수정될 때마다 서버를 자동으로 재시작합니다.
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3) API 문서 확인
서버 실행 후 브라우저에서 아래 주소로 접속하면 자동으로 생성된 문서를 볼 수 있습니다.
*   **Swagger UI**: `http://localhost:8000/docs`
*   **ReDoc**: `http://localhost:8000/redoc`

---

## 3. 초기 프로젝트 구조 (`web-server/main.py`)

```python
from fastapi import FastAPI

app = FastAPI(title="Gilbot API Server")

@app.get("/")
async def root():
    return {"message": "Welcome to Gilbot API Server"}
```

---

## 4. 노션 연동 (배치 결과)

*   **ActionDB**: [백엔드 서버 프레임워크 구축 (FastAPI)] 항목 생성 요청 완료.
*   **KnowledgeDB**: 본 가이드 문서 내용을 노션 기술 문서로 저장 요청 완료.

*(참고: 노션 API 토큰 권한 문제로 자동 배치가 실패할 경우, 위 내용을 복사하여 노션에 수동으로 백업해 두는 것을 권장합니다.)*
