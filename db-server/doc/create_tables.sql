-- ============================================================
-- gilbot DB - CREATE TABLE SQL (v3.1)
-- 수정 사항: 수량(qty) 필드 삭제, 열 번호(col_num) 삭제, 상태 기반 모델로 단순화
-- 프로젝트: 편의점 매대 관리 로봇 (Gilbot)
-- 작성일: 2026-03-27
-- ============================================================

USE gilbot;

SET FOREIGN_KEY_CHECKS = 0;

-- 기존 테이블 삭제
DROP TABLE IF EXISTS alert, detection_log, shelf_status, inventory_status, waypoint_product_plan, 
                     slot_history, slot, waypoint, product_master, patrol_log, patrol_config;

SET FOREIGN_KEY_CHECKS = 1;

-- 1. product_master (제품 마스터 정보)
CREATE TABLE product_master (
    product_id     INT AUTO_INCREMENT PRIMARY KEY,
    product_name   VARCHAR(100) NOT NULL  COMMENT '제품명',
    category       VARCHAR(50)  NOT NULL  COMMENT '분류 (snack, drink 등)',
    barcode        VARCHAR(50)  UNIQUE    COMMENT '제품 자체의 바코드',
    min_inventory_qty INT DEFAULT 0        COMMENT '최소 유지 갯수 (창고 기준)',
    current_inventory_qty INT DEFAULT 0    COMMENT '현재 창고 재고 수량'
) ENGINE=InnoDB CHARACTER SET utf8mb4;

-- 2. waypoint (로봇 정지 및 스캔 위치)
CREATE TABLE waypoint (
    waypoint_id  INT AUTO_INCREMENT PRIMARY KEY,
    waypoint_no  INT NOT NULL UNIQUE       COMMENT '웨이포인트 번호 (로봇 제어용)',
    waypoint_name VARCHAR(50)              COMMENT '위치 별칭 (예: Snack-A)',
    loc_x        FLOAT NOT NULL            COMMENT '지도 상 X 좌표 (m)',
    loc_y        FLOAT NOT NULL            COMMENT '지도 상 Y 좌표 (m)',
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB CHARACTER SET utf8mb4;

-- 3. slot (웨이포인트 별 진열 공간 - 바코드 태그 기반)
CREATE TABLE slot (
    slot_id      INT AUTO_INCREMENT PRIMARY KEY,
    waypoint_id  INT NOT NULL              COMMENT '정지 위치 참조',
    row_num      INT DEFAULT 1             COMMENT '단(Tier) 번호 (1단, 2단 등)',
    product_id   INT                       COMMENT '현재 이 슬롯의 제품',
    barcode_tag  VARCHAR(50) UNIQUE        COMMENT '매대에 부착된 슬롯 식별 바코드(태그)',
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (waypoint_id) REFERENCES waypoint(waypoint_id),
    FOREIGN KEY (product_id)  REFERENCES product_master(product_id)
) ENGINE=InnoDB CHARACTER SET utf8mb4;

-- 4. waypoint_product_plan (위치별 상품 배치 계획)
CREATE TABLE waypoint_product_plan (
    plan_id      INT AUTO_INCREMENT PRIMARY KEY,
    waypoint_id  INT NOT NULL,
    slot_id      INT NOT NULL,
    product_id   INT NOT NULL,
    FOREIGN KEY (waypoint_id) REFERENCES waypoint(waypoint_id),
    FOREIGN KEY (slot_id)     REFERENCES slot(slot_id),
    FOREIGN KEY (product_id)  REFERENCES product_master(product_id)
) ENGINE=InnoDB CHARACTER SET utf8mb4;

-- 5. shelf_status (실시간 진열 현황 - 최종 인식 결과)
CREATE TABLE shelf_status (
    status_id       INT AUTO_INCREMENT PRIMARY KEY,
    waypoint_id     INT NOT NULL,
    slot_id         INT NOT NULL,
    product_id      INT NOT NULL,
    status          ENUM('정상','상품 미진열','오진열') NOT NULL COMMENT '계획 대비 상태',
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (waypoint_id) REFERENCES waypoint(waypoint_id),
    FOREIGN KEY (slot_id)      REFERENCES slot(slot_id),
    FOREIGN KEY (product_id)   REFERENCES product_master(product_id)
) ENGINE=InnoDB CHARACTER SET utf8mb4;

-- 6. patrol_log (순찰 회차 기록)
CREATE TABLE patrol_log (
    patrol_id           INT AUTO_INCREMENT PRIMARY KEY,
    start_time          DATETIME NOT NULL,
    end_time            DATETIME,
    status              ENUM('진행중','완료','중단') DEFAULT '진행중',
    scanned_slots       INT DEFAULT 0           COMMENT '인식 시도한 총 슬롯 수',
    error_found         INT DEFAULT 0           COMMENT '미진열/오진열 발견 수'
) ENGINE=InnoDB CHARACTER SET utf8mb4;

-- 7. detection_log (인식 상세 이력)
CREATE TABLE detection_log (
    log_id            INT AUTO_INCREMENT PRIMARY KEY,
    patrol_id         INT NOT NULL,
    waypoint_id       INT NOT NULL,
    slot_id           INT,
    product_id        INT,
    detected_barcode  VARCHAR(50)      COMMENT '인식된 제품 바코드',
    tag_barcode       VARCHAR(50)      COMMENT '인식된 매대 태그 바코드',
    confidence        FLOAT,
    result            ENUM('정상','상품 미진열','오진열') NOT NULL,
    odom_x            FLOAT,
    odom_y            FLOAT,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patrol_id)   REFERENCES patrol_log(patrol_id),
    FOREIGN KEY (waypoint_id) REFERENCES waypoint(waypoint_id),
    FOREIGN KEY (slot_id)     REFERENCES slot(slot_id)
) ENGINE=InnoDB CHARACTER SET utf8mb4;

-- 8. alert (이상 감제 알림)
CREATE TABLE alert (
    alert_id    INT AUTO_INCREMENT PRIMARY KEY,
    patrol_id   INT NOT NULL,
    waypoint_id INT NOT NULL,
    slot_id     INT,
    product_id  INT NOT NULL,
    alert_type  ENUM('상품 미진열','오진열','수정필요') NOT NULL,
    message     TEXT,
    is_resolved BOOLEAN  DEFAULT FALSE,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patrol_id)   REFERENCES patrol_log(patrol_id),
    FOREIGN KEY (waypoint_id) REFERENCES waypoint(waypoint_id),
    FOREIGN KEY (slot_id)     REFERENCES slot(slot_id),
    FOREIGN KEY (product_id)  REFERENCES product_master(product_id)
) ENGINE=InnoDB CHARACTER SET utf8mb4;


-- 10. patrol_config (로봇 운영 및 스케줄 설정)
CREATE TABLE patrol_config (
    config_id             INT AUTO_INCREMENT PRIMARY KEY,
    avoidance_wait_time   INT DEFAULT 5           COMMENT '회피 대기 시간 (초)',
    patrol_start_time     TIME NOT NULL           COMMENT '순찰 시작 가능 시각',
    patrol_end_time       TIME NOT NULL           COMMENT '순찰 종료 시각 (현장컴 전용)',
    interval_hour         INT DEFAULT 1           COMMENT '순찰 주기 (시간)',
    interval_minute       INT DEFAULT 0           COMMENT '순찰 주기 (분)',
    is_active             BOOLEAN DEFAULT TRUE,
    last_updated          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB CHARACTER SET utf8mb4;
