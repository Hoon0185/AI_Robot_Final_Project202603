-- ============================================================
-- gilbot DB - CREATE TABLE SQL
-- 프로젝트: 편의점 매대 관리 로봇
-- 작성일: 2026-03-24 | 수정: v2.2 (slot 동적 관리 추가)
-- DB: gilbot (CHARACTER SET utf8mb4)
-- ============================================================
-- 테이블 생성 순서 (외래키 의존 순):
--   1. product_master → 2. shelf → 3. slot → 4. slot_history
--   → 5. shelf_product → 6. inventory_status → 7. detection_log
--   → 8. waypoint → 9. patrol_log → 10. alert
-- ============================================================

USE gilbot;

-- ------------------------------------------------------------
-- 1. product_master (외부 재고 DB 동기화 캐시)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS product_master (
    product_id     INT AUTO_INCREMENT PRIMARY KEY,
    product_name   VARCHAR(100) NOT NULL  COMMENT '제품명',
    category       VARCHAR(50)  NOT NULL  COMMENT 'snack / bottle / etc',
    barcode        VARCHAR(50)            COMMENT '제품 바코드',
    standard_qty   INT DEFAULT 0          COMMENT '기준 진열 수량',
    last_synced_at DATETIME               COMMENT '외부DB 동기화 시각'
) CHARACTER SET utf8mb4;

-- ------------------------------------------------------------
-- 2. shelf (매대 - 위치 기준점)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shelf (
    shelf_id   INT AUTO_INCREMENT PRIMARY KEY,
    shelf_no   INT          NOT NULL COMMENT '매대 번호 (예: 1, 2, 3)',
    shelf_name VARCHAR(20)  NOT NULL COMMENT '매대 이름 (예: A, B, C)',
    total_rows INT DEFAULT 0         COMMENT '총 행 수 (참고용, 동적 변경 가능)',
    total_cols INT DEFAULT 0         COMMENT '총 열 수 (참고용, 동적 변경 가능)',
    loc_x      FLOAT        NOT NULL COMMENT 'X 좌표 (미터, 로봇 기준)',
    loc_y      FLOAT        NOT NULL COMMENT 'Y 좌표 (미터, 로봇 기준)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_shelf_no (shelf_no)
) CHARACTER SET utf8mb4;

-- ------------------------------------------------------------
-- 3. slot (바코드 기반 동적 슬롯 - 핵심 테이블)
-- 바코드 감지 시 자동 생성/수정/비활성화
-- 슬롯 = 매대번호 + 행 + 열 + 바코드 위치(odom)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS slot (
    slot_id      INT AUTO_INCREMENT PRIMARY KEY,
    shelf_id     INT          NOT NULL COMMENT '소속 매대',
    row_num      INT          COMMENT '행 번호 (바코드 감지 기반, 1부터)',
    col_num      INT          COMMENT '열 번호 (바코드 감지 기반, 1부터)',
    product_id   INT          COMMENT '현재 이 슬롯의 제품 (NULL = 비어있음)',
    barcode      VARCHAR(50)  COMMENT '슬롯 식별 바코드 값',
    odom_x       FLOAT        COMMENT '바코드 최초/최근 감지 시점 로봇 X 위치',
    odom_y       FLOAT        COMMENT '바코드 최초/최근 감지 시점 로봇 Y 위치',
    status       ENUM('active','empty','moved','deleted') DEFAULT 'active'
                              COMMENT 'active=정상 / empty=빈자리 / moved=이동됨 / deleted=삭제됨',
    first_seen   DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '최초 감지 시각',
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (shelf_id)   REFERENCES shelf(shelf_id),
    FOREIGN KEY (product_id) REFERENCES product_master(product_id)
) CHARACTER SET utf8mb4;

-- ------------------------------------------------------------
-- 4. slot_history (슬롯 변경 이력 - 이동/삭제/추가 추적)
-- 회사 정책으로 상품이 이동/추가/제거될 때마다 기록
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS slot_history (
    history_id     INT AUTO_INCREMENT PRIMARY KEY,
    slot_id        INT NOT NULL               COMMENT '변경된 슬롯',
    change_type    ENUM('created','moved','product_changed','empty','deleted') NOT NULL
                                              COMMENT '변경 유형',
    old_shelf_id   INT    COMMENT '이전 매대',
    old_row_num    INT    COMMENT '이전 행',
    old_col_num    INT    COMMENT '이전 열',
    old_product_id INT    COMMENT '이전 제품',
    new_shelf_id   INT    COMMENT '새 매대',
    new_row_num    INT    COMMENT '새 행',
    new_col_num    INT    COMMENT '새 열',
    new_product_id INT    COMMENT '새 제품',
    changed_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (slot_id) REFERENCES slot(slot_id)
) CHARACTER SET utf8mb4;

-- ------------------------------------------------------------
-- 5. shelf_product (매대-제품 기대 배치 - 관리자 설정)
-- slot은 로봇이 실제 감지한 것, shelf_product는 있어야 할 것
-- 둘을 비교해서 이상 감지
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shelf_product (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    shelf_id     INT NOT NULL,
    product_id   INT NOT NULL,
    expected_qty INT DEFAULT 0 COMMENT '기대 진열 수량',
    FOREIGN KEY (shelf_id)   REFERENCES shelf(shelf_id)            ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES product_master(product_id) ON DELETE CASCADE
) CHARACTER SET utf8mb4;

-- ------------------------------------------------------------
-- 6. inventory_status (실시간 재고 현황 - slot 기반 최신화)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inventory_status (
    status_id       INT AUTO_INCREMENT PRIMARY KEY,
    slot_id         INT NOT NULL               COMMENT '슬롯 참조 (위치 정보)',
    shelf_id        INT NOT NULL,
    product_id      INT NOT NULL,
    current_qty     INT DEFAULT 0              COMMENT '현재 인식된 수량',
    status          ENUM('있다','없다','다른제품') NOT NULL,
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (slot_id)    REFERENCES slot(slot_id),
    FOREIGN KEY (shelf_id)   REFERENCES shelf(shelf_id),
    FOREIGN KEY (product_id) REFERENCES product_master(product_id)
) CHARACTER SET utf8mb4;

-- ------------------------------------------------------------
-- 7. detection_log (영상 인식 이력 - 누적, slot 기반)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS detection_log (
    log_id            INT AUTO_INCREMENT PRIMARY KEY,
    slot_id           INT  COMMENT '인식된 슬롯 (신규 슬롯이면 NULL 후 생성)',
    shelf_id          INT  NOT NULL,
    product_id        INT  COMMENT '인식 실패 시 NULL',
    detected_category VARCHAR(50)  COMMENT 'YOLO 1차 분류 결과',
    detected_product  VARCHAR(100) COMMENT 'Keras 2차 식별 결과',
    barcode_value     VARCHAR(50)  COMMENT '감지된 바코드 원본 값',
    confidence        FLOAT        COMMENT '인식 신뢰도 (0.0 ~ 1.0)',
    result            ENUM('있다','없다','다른제품') NOT NULL,
    odom_x            FLOAT        COMMENT '감지 시점 로봇 X 위치 (raw odom)',
    odom_y            FLOAT        COMMENT '감지 시점 로봇 Y 위치 (raw odom)',
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (slot_id)  REFERENCES slot(slot_id),
    FOREIGN KEY (shelf_id) REFERENCES shelf(shelf_id)
) CHARACTER SET utf8mb4;

-- ------------------------------------------------------------
-- 8. waypoint (순찰 정지 지점)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS waypoint (
    waypoint_id INT AUTO_INCREMENT PRIMARY KEY,
    shelf_id    INT     NOT NULL,
    order_num   INT     NOT NULL COMMENT '순찰 순서',
    robot_x     FLOAT   NOT NULL COMMENT '로봇 정지 X 좌표',
    robot_y     FLOAT   NOT NULL COMMENT '로봇 정지 Y 좌표',
    is_active   BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (shelf_id) REFERENCES shelf(shelf_id)
) CHARACTER SET utf8mb4;

-- ------------------------------------------------------------
-- 9. patrol_log (순찰 회차 기록)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patrol_log (
    patrol_id           INT AUTO_INCREMENT PRIMARY KEY,
    start_time          DATETIME NOT NULL,
    end_time            DATETIME              COMMENT '완료 전 NULL',
    status              ENUM('진행중','완료','중단') DEFAULT '진행중',
    total_waypoints     INT DEFAULT 0,
    completed_waypoints INT DEFAULT 0
) CHARACTER SET utf8mb4;

-- ------------------------------------------------------------
-- 10. alert (재고 알림)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alert (
    alert_id    INT AUTO_INCREMENT PRIMARY KEY,
    slot_id     INT          COMMENT '슬롯 참조 (위치 특정 가능)',
    shelf_id    INT NOT NULL,
    product_id  INT NOT NULL,
    alert_type  ENUM('재고부족','품절','이상감지','슬롯변경') NOT NULL,
    message     TEXT,
    is_resolved BOOLEAN  DEFAULT FALSE,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (slot_id)    REFERENCES slot(slot_id),
