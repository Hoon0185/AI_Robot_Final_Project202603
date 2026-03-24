# 🔄 슬롯 자동 업데이트 로직

> **연관 파일:** [`erd.md`](./erd.md) | [`create_tables.sql`](./create_tables.sql)  
> **작성일:** 2026-03-24  

---

## 개요

순찰(patrol) 중 바코드를 감지할 때마다 **슬롯(slot) 상태를 자동으로 업데이트**합니다.  
회사 정책으로 상품이 이동/추가/제거되더라도 다음 순찰에서 자동으로 DB가 최신화됩니다.

---

## 전체 흐름도

```
[순찰 시작]
    │
    ▼
patrol_log INSERT  →  patrol_id 발급
    │
    ▼ (각 waypoint 순회)
┌──────────────────────────────────────────┐
│  바코드 감지 (YOLO + 바코드 리더)         │
│                                          │
│  [바코드 값으로 slot 테이블 조회]         │
│                                          │
│  ┌── 케이스 A: 같은 위치에 동일 바코드   │
│  │   → slot.status = 'active' 유지       │
│  │   → slot.odom_x/y 갱신               │
│  │                                       │
│  ├── 케이스 B: 다른 위치에서 동일 바코드  │
│  │   → slot.status = 'moved'            │
│  │   → slot.odom_x/y 새 위치로 갱신     │
│  │   → slot_history INSERT (moved)      │
│  │   → alert INSERT (슬롯변경)          │
│  │                                       │
│  └── 케이스 C: 바코드가 DB에 없음        │
│      → slot INSERT (신규)               │
│      → slot_history INSERT (created)   │
│                                          │
│  detection_log INSERT (patrol_id 포함)   │
└──────────────────────────────────────────┘
    │
    ▼ (순찰 완료)
[이번 순찰에서 감지 안 된 slot 탐색]
    │
    │  SQL:
    │  SELECT s.slot_id FROM slot s
    │  WHERE s.status = 'active'
    │    AND s.slot_id NOT IN (
    │      SELECT DISTINCT slot_id FROM detection_log
    │      WHERE patrol_id = [현재 patrol_id]
    │      AND   slot_id IS NOT NULL
    │    )
    │
    ▼
[미감지 슬롯 처리]
    │
    ├── 1회 연속 미감지 → status = 'empty' + alert(재고부족)
    └── 2회 이상 연속 미감지 → status = 'deleted' + alert(품절)
         + slot_history INSERT (deleted)

[patrol_log UPDATE]
    → end_time, status='완료'
    → new_slots, moved_slots, missing_slots 집계
```

---

## 웹 서버 처리 로직 (Python 의사코드)

```python
def process_patrol_complete(patrol_id):
    """순찰 완료 시 호출 — 슬롯 자동 업데이트"""

    # 1. 이번 순찰에서 감지된 slot_id 목록
    scanned_slots = db.query("""
        SELECT DISTINCT slot_id FROM detection_log
        WHERE patrol_id = %s AND slot_id IS NOT NULL
    """, patrol_id)

    # 2. 이전까지 active 상태였던 모든 슬롯
    active_slots = db.query("""
        SELECT slot_id FROM slot WHERE status = 'active'
    """)

    # 3. 이번 순찰에서 못 본 슬롯
    missing = set(active_slots) - set(scanned_slots)

    for slot_id in missing:
        slot = db.get_slot(slot_id)

        if slot.miss_count >= 1:
            # 2회 이상 미감지 → 삭제 처리
            db.update_slot(slot_id, status='deleted')
            db.insert_slot_history(slot_id, change_type='deleted')
            db.insert_alert(slot_id, alert_type='품절')
        else:
            # 1회 미감지 → 빈자리 처리
            db.update_slot(slot_id, status='empty')
            db.insert_alert(slot_id, alert_type='재고부족')

    # 4. 신규/이동 슬롯 집계 → patrol_log 업데이트
    db.update_patrol_log(patrol_id,
        end_time=now(),
        status='완료',
        new_slots=count_new,
        moved_slots=count_moved,
        missing_slots=len(missing)
    )


def process_barcode_detection(patrol_id, barcode, odom_x, odom_y, shelf_id):
    """바코드 감지 시 호출 — 슬롯 생성/업데이트"""

    existing_slot = db.find_slot_by_barcode(barcode)

    if existing_slot is None:
        # 케이스 C: 신규 슬롯
        slot_id = db.insert_slot(
            shelf_id=shelf_id, barcode=barcode,
            odom_x=odom_x, odom_y=odom_y, status='active'
        )
        db.insert_slot_history(slot_id, change_type='created')

    elif is_different_position(existing_slot, odom_x, odom_y):
        # 케이스 B: 위치 이동
        db.insert_slot_history(existing_slot.slot_id, change_type='moved',
            old_odom_x=existing_slot.odom_x, old_odom_y=existing_slot.odom_y)
        db.update_slot(existing_slot.slot_id,
            odom_x=odom_x, odom_y=odom_y, status='moved')
        db.insert_alert(existing_slot.slot_id, alert_type='슬롯변경')
    else:
        # 케이스 A: 정상 감지 (동일 위치)
        db.update_slot(existing_slot.slot_id, status='active',
            odom_x=odom_x, odom_y=odom_y)

    # detection_log 항상 기록
    db.insert_detection_log(patrol_id=patrol_id, slot_id=slot_id, ...)
```

---

## 슬롯 상태 전이 다이어그램

```
                 [신제품 입고]
                      │
                      ▼
                  [ created ]
                      │
                      ▼
                  [ active ]  ◀────────────────────┐
                 /    │    \                        │
                /     │     \                       │
          [이동]   [감지안됨]  [위치변동]           [재감지]
           /           │           \                │
          ▼            ▼            ▼               │
       [moved]      [empty]      [moved]            │
          │            │                            │
          │        [또 안보임]                      │
          │            │                            │
          └──────▶ [deleted] ──────────────────────┘
                                               (재입고시)
```

---

## 연속 미감지 판단 기준 (권장)

| 연속 미감지 순찰 수 | 처리 |
|---|---|
| 0회 | `active` 유지 |
| 1회 | `empty` → `alert: 재고부족` |
| 2회 이상 | `deleted` → `alert: 품절` |

> 💡 이 기준은 순찰 주기에 따라 조정 필요  
> (예: 10분 단위 순찰이면 2회 = 20분 이상 미감지)

---

## 관련 파일

| 파일 | 내용 |
|---|---|
| [`erd.md`](./erd.md) | ERD 다이어그램 |
| [`create_tables.sql`](./create_tables.sql) | 테이블 생성 SQL |
| [`how_to_view_erd.md`](./how_to_view_erd.md) | ERD 보는 법 |
| [`slot_update_logic.md`](./slot_update_logic.md) | 이 파일 |
