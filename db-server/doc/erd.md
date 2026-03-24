# 📊 ERD — gilbot DB

> **프로젝트:** 편의점 매대 관리 로봇  
> **DB명:** `gilbot`  
> **서버:** Amazon Lightsail `16.184.56.119`  
> **작성일:** 2026-03-24  
> **작성자:** DB/WEB 파트  

---

## 설계 원칙

| 테이블 | 역할 |
|---|---|
| `product_master` | 외부 재고관리 DB에서 필요한 필드만 **동기화 캐시** (직접 접근 불가 대응) |
| `shelf` | 매대/진열대 위치 좌표 (로봇 waypoint와 연결) |
| `shelf_product` | 매대-제품 배치 매핑 (어느 매대에 어떤 제품이 있어야 하는가) |
| `inventory_status` | 로봇 인식 결과 기반 **실시간 재고 현황** (최신화 방식) |
| `detection_log` | 매 인식마다 쌓이는 이력 로그 (inventory_status와 분리) |
| `waypoint` | 순찰 경로상 각 매대 로봇 정지 위치 |
| `patrol_log` | 순찰 회차 기록 (시작/종료/완료 웨이포인트 수) |
| `alert` | 재고 부족 / 품절 / 이상 감지 알림 |

---

## ERD 다이어그램

```mermaid
erDiagram
    product_master {
        INT product_id PK
        VARCHAR product_name
        VARCHAR category
        VARCHAR barcode
        INT standard_qty
        DATETIME last_synced_at
    }

    shelf {
        INT shelf_id PK
        INT shelf_no "매대 번호"
        VARCHAR shelf_name "매대 이름"
        INT total_rows "총 행 수"
        INT total_cols "총 열 수"
        FLOAT loc_x "X 좌표"
        FLOAT loc_y "Y 좌표"
        DATETIME created_at
    }

    shelf_product {
        INT id PK
        INT shelf_id FK
        INT product_id FK
        INT row_num "행 번호"
        INT col_num "열 번호"
        INT expected_qty
    }

    inventory_status {
        INT status_id PK
        INT shelf_id FK
        INT product_id FK
        INT current_qty
        ENUM status
        DATETIME last_updated_at
    }

    detection_log {
        INT log_id PK
        INT shelf_id FK
        INT product_id FK
        VARCHAR detected_category
        VARCHAR detected_product
        FLOAT confidence
        ENUM result
        DATETIME created_at
    }

    waypoint {
        INT waypoint_id PK
        INT shelf_id FK
        INT order_num
        FLOAT robot_x
        FLOAT robot_y
        BOOLEAN is_active
    }

    patrol_log {
        INT patrol_id PK
        DATETIME start_time
        DATETIME end_time
        ENUM status
        INT total_waypoints
        INT completed_waypoints
    }

    alert {
        INT alert_id PK
        INT shelf_id FK
        INT product_id FK
        ENUM alert_type
        TEXT message
        BOOLEAN is_resolved
        DATETIME created_at
    }

    product_master ||--o{ shelf_product    : "진열 제품"
    shelf          ||--o{ shelf_product    : "배치 정보"
    product_master ||--o{ inventory_status : "추적 대상"
    shelf          ||--o{ inventory_status : "재고 현황"
    product_master ||--o{ detection_log    : "인식 제품"
    shelf          ||--o{ detection_log    : "인식 위치"
    shelf          ||--o{ waypoint         : "정지 포인트"
    product_master ||--o{ alert            : "알림 대상"
    shelf          ||--o{ alert            : "알림 발생"
```

---

## 외부 재고 DB 연동 전략

```
[외부 재고관리 DB] (접근 불가)
  제품명, 종류, 바코드, 기준수량 등
          ↓  sync_product.py (수동 or 주기 실행)
[gilbot DB - product_master 테이블]
  캐시로 저장 → robot / web 시스템이 이를 참조
```

**동기화 방법 (우선순위):**
1. 관리자가 CSV로 내보내기 → `sync_product.py`로 import
2. (가능하다면) 외부 DB API 호출 → 자동 동기화

---

## JSON 전송 스펙 (로봇 → 웹 서버)

```json
{
  "shelf_id": 1,
  "product_id": 42,
  "detected_category": "snack",
  "detected_product": "포카칩 오리지널",
  "confidence": 0.94,
  "result": "있다",
  "timestamp": "2026-03-24T12:00:00"
}
```

---

## CREATE TABLE SQL

전체 SQL은 [`create_tables.sql`](./create_tables.sql) 파일 참조
