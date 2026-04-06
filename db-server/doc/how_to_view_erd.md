# 🗺️ ERD 보는 법 가이드

> **대상 파일:** [`erd.md`](./erd.md)  
> **사용 도구:** VSCode + Mermaid 플러그인

---

## 1. 플러그인 설치

### VSCode Extensions에서 설치
1. `Ctrl+Shift+X` → Extensions 열기
2. **`mermaid`** 검색
3. **"Markdown Preview Mermaid Support"** (`bierner.markdown-mermaid`) 설치

### 터미널에서 설치
```bash
code --install-extension bierner.markdown-mermaid
```

---

## 2. ERD 미리보기

1. `erd.md` 파일 열기
2. `Ctrl+Shift+V` → Markdown 미리보기 창 열기
3. 미리보기 창에서 ERD 다이어그램이 자동 렌더링됨

> 💡 **Tip:** 편집창과 미리보기를 나란히 보려면  
> `Ctrl+K V` 단축키 사용

---

## 3. Mermaid ERD 표기법 읽는 법

### 3-1. 테이블(Entity) 구조

```
테이블명 {
    타입  컬럼명  키타입  "설명"
}
```

**예시:**
```mermaid
erDiagram
    shelf {
        INT shelf_id PK
        INT shelf_no "매대 번호"
        VARCHAR shelf_name "매대 이름"
    }
```

| 기호 | 의미 |
|---|---|
| `PK` | Primary Key (기본키) |
| `FK` | Foreign Key (외래키) |
| `INT` | 정수형 |
| `VARCHAR` | 문자열 |
| `FLOAT` | 실수형 |
| `DATETIME` | 날짜+시간 |
| `ENUM` | 열거형 (정해진 값만 허용) |
| `BOOLEAN` | 참/거짓 |

---

### 3-2. 관계선(Relationship) 읽는 법

```
테이블A  관계  테이블B : "관계설명"
```

#### 관계 기호표

| 기호 | 의미 | 예시 |
|---|---|---|
| `\|\|` | 정확히 1 | 반드시 1개 |
| `o\|` | 0 또는 1 | 없거나 1개 |
| `\|{` | 1 이상 | 1개 이상 |
| `o{` | 0 이상 | 없거나 여러 개 |

#### 자주 쓰는 조합

| 표기 | 읽는 법 | 뜻 |
|---|---|---|
| `\|\|--o{` | 일 대 다 | 1개 ↔ 0개 이상 |
| `\|\|--\|\|` | 일 대 일 | 1개 ↔ 1개 |
| `o{--o{` | 다 대 다 | 여러 개 ↔ 여러 개 |

#### 예시 해석

```
shelf ||--o{ shelf_product : "배치 정보"
```
> **매대(shelf) 1개**는 **진열 정보(shelf_product) 0개 이상**을 가질 수 있다.  
> = 하나의 매대에 여러 제품이 배치될 수 있음

```
product_master ||--o{ shelf_status : "추적 대상"
```
> **제품(product_master) 1개**는 **매대 현황(shelf_status) 0개 이상**을 가질 수 있다.  
> = 한 제품의 진열 상태가 여러 매대에 걸쳐 기록될 수 있음

---

## 4. gilbot DB 테이블 한눈에 보기 (v3.3)

```mermaid
flowchart LR
    EXT(["&#x1F4E6; 외부 재고 DB"]) -- "동기화 (yolo_class_id)" --> PM["product_master\n(제품정보 + YOLO ID)"]

    PM --> SP["waypoint_product_plan\n(기대 배치)"]
    PM --> SS["shelf_status\n(실시간 진열현황)"]
    PM --> AL["alert\n(알림)"]

    WP["waypoint\n(순찰 정지위치)"] --> SP
    WP --> SS
    WP --> DL["detection_log\n(인식 로그)"]
    WP --> AL

    DL --> SS
    DL --> AL

    PL["patrol_log\n(순찰 기록)"] --> DL
    PC["patrol_config\n(운영 설정)"] --> PL
```

---

## 5. 위치 좌표 개념

### 매대(shelf) 위치 — 로봇 기준 좌표

- `loc_x`, `loc_y` : 로봇이 해당 매대 앞에 멈출 위치 (미터 단위)

```mermaid
quadrantChart
    title 매대 배치도 (예시)
    x-axis 0 --> 5
    y-axis 0 --> 5
    quadrant-1 구역A
    quadrant-2 구역B
    quadrant-3 구역C
    quadrant-4 구역D
    매대1: [0.5, 0.5]
    매대2: [0.5, 2.5]
    매대3: [2.5, 0.5]
    로봇시작점: [0.1, 0.1]
```

### 매대 내 제품 위치 — 바코드 태그 기반 (v3.3)

> ⚠️ 위치는 물리적인 **바코드 태그(`barcode_tag`)**를 기준으로 식별됩니다.

| | 열1 | 열2 | 열3 |
|---|---|---|---|
| **1단 (row_num=1)** | 맛동산 🏷️ | 죠리퐁 🏷️ | 포스틱 🏷️ |
| **2단 (row_num=2)** | 스프라이트 🏷️ | _(빈칸)_ | 포카리 🏷️ |

> 🏷️ = 바코드 태그 위치 → `waypoint_product_plan.barcode_tag` 에 정의

---

## 6. 관련 파일

| 파일 | 설명 |
|---|---|
| [`erd.md`](./erd.md) | ERD 다이어그램 및 설계 원칙 |
| [`create_tables.sql`](./create_tables.sql) | MySQL 테이블 생성 SQL |
| [`how_to_view_erd.md`](./how_to_view_erd.md) | 이 파일 |
