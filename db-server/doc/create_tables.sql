-- ============================================================
-- gilbot DB - CREATE TABLE SQL
-- 프로젝트: 편의점 매대 관리 로봇
-- 작성일: 2026-03-24
-- DB: gilbot (CHARACTER SET utf8mb4)
-- ============================================================

USE gilbot;

-- 1. product_master (외부 재고 DB 동기화 캐시)
CREATE TABLE IF NOT EXISTS product_master (
    product_id     INT AUTO_INCREMENT PRIMARY KEY,
    product_name   VARCHAR(100) NOT NULL  COMMENT '제품명',
    category       VARCHAR(50)  NOT NULL  COMMENT 'snack / bottle / etc',
    barcode        VARCHAR(50)            COMMENT '바코드',
    standard_qty   INT DEFAULT 0          COMMENT '기준 진열 수량',
    last_synced_at DATETIME               COMMENT '외부DB 동기화 시각'
) CHARACTER SET utf8mb4;

-- 2. shelf (진열대/매대 위치)
CREATE TABLE IF NOT EXISTS shelf (
    shelf_id   INT AUTO_INCREMENT PRIMARY KEY,
    shelf_no   INT          NOT NULL COMMENT '매대 번호 (예: 1, 2, 3)',
    shelf_name VARCHAR(20)  NOT NULL COMMENT '매대 이름 (예: A, B, C)',
    total_rows INT DEFAULT 0         COMMENT '총 행 수',
    total_cols INT DEFAULT 0         COMMENT '총 열 수',
    loc_x      FLOAT        NOT NULL COMMENT 'X 좌표 (미터, 로봇 기준)',
    loc_y      FLOAT        NOT NULL COMMENT 'Y 좌표 (미터, 로봇 기준)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_shelf_no (shelf_no)
) CHARACTER SET utf8mb4;

-- 3. shelf_product (매대-제품 매핑 - 어떤 매대에 어떤 제품이 있어야 하는지 포괄적 관리)
-- ⚠️  개정: 행/열(row/col) 슬롯 방식 폐기 → 바코드+odom 방식으로 위치 판단
CREATE TABLE IF NOT EXISTS shelf_product (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    shelf_id     INT NOT NULL,
    product_id   INT NOT NULL,
    expected_qty INT DEFAULT 0 COMMENT '기대 진열 수량',
    FOREIGN KEY (shelf_id)   REFERENCES shelf(shelf_id)            ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES product_master(product_id) ON DELETE CASCADE
) CHARACTER SET utf8mb4;

-- 4. inventory_status (실시간 재고 현황 - 최신화 방식)
-- 핵심: odom_x, odom_y = 바코드 괐 시점의 로봇 실제 위치 저장
CREATE TABLE IF NOT EXISTS inventory_status (
    status_id       INT AUTO_INCREMENT PRIMARY KEY,
    shelf_id        INT NOT NULL,
    product_id      INT NOT NULL,
    current_qty     INT DEFAULT 0 COMMENT '현재 인식된 수량',
    status          ENUM('있다','없다','다른제품') NOT NULL,
    odom_x          FLOAT COMMENT '바코드 괐 시점 로봇 X 위치 (odom)',
    odom_y          FLOAT COMMENT '바코드 괐 시점 로봇 Y 위치 (odom)',
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (shelf_id)   REFERENCES shelf(shelf_id),
    FOREIGN KEY (product_id) REFERENCES product_master(product_id)
) CHARACTER SET utf8mb4;

-- 5. detection_log (영상 인식 이력 로그 - 누적 방식)
-- 핵심: odom_x, odom_y = 바코드 괐 시점의 로봇 실제 위치
CREATE TABLE IF NOT EXISTS detection_log (
    log_id            INT AUTO_INCREMENT PRIMARY KEY,
    shelf_id          INT  NOT NULL,
    product_id        INT  COMMENT '인식 실패 시 NULL',
    detected_category VARCHAR(50)  COMMENT 'YOLO 1차 분류 결과',
    detected_product  VARCHAR(100) COMMENT 'Keras 2차 식별 결과',
    confidence        FLOAT        COMMENT '인식 신뢰도 (0.0 ~ 1.0)',
    result            ENUM('있다','없다','다른제품') NOT NULL,
    odom_x            FLOAT COMMENT '바코드 괐 시점 로봇 X 위치 (odom)',
    odom_y            FLOAT COMMENT '바코드 괐 시점 로봇 Y 위치 (odom)',
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shelf_id) REFERENCES shelf(shelf_id)
) CHARACTER SET utf8mb4;

-- 6. waypoint (순찰 정지 지점)
CREATE TABLE IF NOT EXISTS waypoint (
    waypoint_id INT AUTO_INCREMENT PRIMARY KEY,
    shelf_id    INT     NOT NULL,
    order_num   INT     NOT NULL COMMENT '순찰 순서',
    robot_x     FLOAT   NOT NULL COMMENT '로봇 정지 X 좌표',
    robot_y     FLOAT   NOT NULL COMMENT '로봇 정지 Y 좌표',
    is_active   BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (shelf_id) REFERENCES shelf(shelf_id)
) CHARACTER SET utf8mb4;

-- 7. patrol_log (순찰 회차 기록)
CREATE TABLE IF NOT EXISTS patrol_log (
    patrol_id           INT AUTO_INCREMENT PRIMARY KEY,
    start_time          DATETIME NOT NULL,
    end_time            DATETIME              COMMENT '완료 전 NULL',
    status              ENUM('진행중','완료','중단') DEFAULT '진행중',
    total_waypoints     INT DEFAULT 0,
    completed_waypoints INT DEFAULT 0
) CHARACTER SET utf8mb4;

-- 8. alert (재고 알림)
CREATE TABLE IF NOT EXISTS alert (
    alert_id    INT AUTO_INCREMENT PRIMARY KEY,
    shelf_id    INT NOT NULL,
    product_id  INT NOT NULL,
    alert_type  ENUM('재고부족','품절','이상감지') NOT NULL,
    message     TEXT,
    is_resolved BOOLEAN  DEFAULT FALSE,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shelf_id)   REFERENCES shelf(shelf_id),
    FOREIGN KEY (product_id) REFERENCES product_master(product_id)
) CHARACTER SET utf8mb4;

-- 확인
SHOW TABLES;
