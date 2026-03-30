-- ============================================================
-- gilbot DB - CREATE TABLE SQL (v3.2)
-- 수정 사항: 사용되지 않는 shelf, slot, shelf_product 관련 필드 및 테이블 완전 삭제
-- 프로젝트: 편의점 매대 관리 로봇 (Gilbot)
-- 작성일: 2026-03-30
-- ============================================================

USE gilbot;

SET FOREIGN_KEY_CHECKS = 0;

-- 기존 테이블 삭제
DROP TABLE IF EXISTS alert, detection_log, shelf_status, waypoint_product_plan, 
                     waypoint, product_master, patrol_log, patrol_config, robot_command;

SET FOREIGN_KEY_CHECKS = 1;

-- 1. product_master (제품 마스터 정보)
CREATE TABLE product_master (
    product_id     INT AUTO_INCREMENT PRIMARY KEY,
    product_name   VARCHAR(100) NOT NULL  COMMENT '제품명',
    category       VARCHAR(50)  NOT NULL  COMMENT '분류 (snack, drink 등)',
    barcode        VARCHAR(50)  UNIQUE    COMMENT '제품 자체의 바코드',
    min_inventory_qty INT DEFAULT 0        COMMENT '최소 유지 갯수 (창고 기준)',
    current_inventory_qty INT DEFAULT 0    COMMENT '현재 창고 재고 수량',
    alert_log       VARCHAR(255) DEFAULT NULL COMMENT '재고 부족 경고 메시지',
    is_alert_resolved BOOLEAN DEFAULT 0    COMMENT '경고 확인 여부'
) ENGINE=InnoDB CHARACTER SET utf8mb4;

-- 2. waypoint (로봇 정지 및 스캔 위치)
CREATE TABLE waypoint (
    waypoint_id  INT AUTO_INCREMENT PRIMARY KEY,
    waypoint_no  INT NOT NULL UNIQUE       COMMENT '웨이포인트 번호 (로봇 제어용)',
    waypoint_name VARCHAR(50)              COMMENT '위치 별칭 (예: Snack-A)',
    loc_x        FLOAT NOT NULL DEFAULT 0.0 COMMENT '지도 상 X 좌표 (m)',
    loc_y        FLOAT NOT NULL DEFAULT 0.0 COMMENT '지도 상 Y 좌표 (m)',
    visit_order  INT DEFAULT 0,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB CHARACTER SET utf8mb4;

-- 3. waypoint_product_plan (위치별 상품 배치 계획)
CREATE TABLE waypoint_product_plan (
    plan_id      INT AUTO_INCREMENT PRIMARY KEY,
    waypoint_id  INT NOT NULL,
    product_id   INT NOT NULL,
    barcode_tag  VARCHAR(50) UNIQUE NOT NULL,
    row_num      INT DEFAULT 1,
    plan_order   INT DEFAULT 0,
    FOREIGN KEY (waypoint_id) REFERENCES waypoint(waypoint_id),
    FOREIGN KEY (product_id)  REFERENCES product_master(product_id)
) ENGINE=InnoDB CHARACTER SET utf8mb4;

-- 4. shelf_status (실시간 진열 현황 - 최종 인식 결과)
CREATE TABLE shelf_status (
    status_id       INT AUTO_INCREMENT PRIMARY KEY,
    waypoint_id     INT NOT NULL,
    barcode_tag     VARCHAR(50),
    product_id      INT NOT NULL,
    status          ENUM('정상','결품','오진열') NOT NULL COMMENT '계획 대비 상태',
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (waypoint_id) REFERENCES waypoint(waypoint_id),
    FOREIGN KEY (product_id)   REFERENCES product_master(product_id)
) ENGINE=InnoDB CHARACTER SET utf8mb4;

-- 5. patrol_log (순찰 회차 기록)
CREATE TABLE patrol_log (
    patrol_id           INT AUTO_INCREMENT PRIMARY KEY,
    start_time          DATETIME NOT NULL,
    end_time            DATETIME,
    status              ENUM('진행중','완료','중단') DEFAULT '진행중',
    scanned_slots       INT DEFAULT 0           COMMENT '인식 시도한 총 슬롯 수',
    error_found         INT DEFAULT 0           COMMENT '미진열/오진열 발견 수'
) ENGINE=InnoDB CHARACTER SET utf8mb4;

-- 6. detection_log (인식 상세 이력)
CREATE TABLE detection_log (
    log_id            INT AUTO_INCREMENT PRIMARY KEY,
    patrol_id         INT NOT NULL,
    waypoint_id       INT NOT NULL,
    product_id        INT,
    detected_barcode  VARCHAR(50)      COMMENT '인식된 제품 바코드',
    tag_barcode       VARCHAR(50)      COMMENT '인식된 매대 태그 바코드',
    confidence        FLOAT,
    result            ENUM('정상','결품','오진열') NOT NULL,
    odom_x            FLOAT,
    odom_y            FLOAT,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patrol_id)   REFERENCES patrol_log(patrol_id),
    FOREIGN KEY (waypoint_id) REFERENCES waypoint(waypoint_id)
) ENGINE=InnoDB CHARACTER SET utf8mb4;

-- 7. alert (이상 감제 알림)
CREATE TABLE alert (
    alert_id    INT AUTO_INCREMENT PRIMARY KEY,
    patrol_id   INT NOT NULL,
    waypoint_id INT NOT NULL,
    barcode_tag VARCHAR(50),
    product_id  INT NOT NULL,
    alert_type  ENUM('결품','오진열','수정필요') NOT NULL,
    message     TEXT,
    is_resolved BOOLEAN  DEFAULT FALSE,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patrol_id)   REFERENCES patrol_log(patrol_id),
    FOREIGN KEY (waypoint_id) REFERENCES waypoint(waypoint_id),
    FOREIGN KEY (product_id)  REFERENCES product_master(product_id)
) ENGINE=InnoDB CHARACTER SET utf8mb4;

-- 8. patrol_config (로봇 운영 및 스케줄 설정)
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

-- 9. robot_command (로봇 원격 제어 명령 큐)
CREATE TABLE robot_command (
    command_id    INT AUTO_INCREMENT PRIMARY KEY,
    command_type  ENUM('START_PATROL', 'RETURN_TO_BASE', 'EMERGENCY_STOP') NOT NULL,
    status        ENUM('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED') DEFAULT 'PENDING',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB CHARACTER SET utf8mb4;
