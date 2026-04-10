import os
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime

# .env 파일 로드
load_dotenv()

def insert_base_data():
    try:
        # DB 연결 정보 (환경 변수 우선, 없으면 기본값)
        db_config = {
            'host': os.getenv('DB_HOST', '16.184.56.119'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'gilbot'),
            'password': os.getenv('DB_PASSWORD', 'robot123'),
            'database': os.getenv('DB_NAME', 'gilbot')
        }

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        print("--- Gilbot 기초 데이터 입력 시작 (Refactored Schema) ---")

        # 1. 외래 키 체크 해제 및 기존 데이터 정리
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        tables = [
            'alert', 'detection_log', 'shelf_status', 
            'waypoint_product_plan', 'waypoint', 
            'product_master', 'patrol_log', 'patrol_config'
        ]
        for table in tables:
            # Check if table exists before truncate (case of slot)
            cursor.execute(f"SHOW TABLES LIKE '{table}'")
            if cursor.fetchone():
                cursor.execute(f"TRUNCATE TABLE {table}")
        
        # 'slot' table is already dropped by migration, but in case of re-run
        cursor.execute("SHOW TABLES LIKE 'slot'")
        if cursor.fetchone():
            cursor.execute("DROP TABLE slot")

        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        print("✅ 기존 테이블 데이터 초기화 완료.")

        # 2. 상품 마스터 등록 (YOLO Class ID 매핑 포함)
        # (id, name, category, barcode, yolo_class_id)
        products = [
            (1, '맛동산', 'snack', '881010101010', 102),
            (2, '죠리퐁', 'snack', '882020202020', 96),
            (3, '포스틱', 'snack', '883030303030', 106),
            (4, '썬칩', 'snack', '884040404040', 108),
            (5, 'C콘칲', 'snack', '885050505050', 93),
            (6, '꼬북칩', 'snack', '886060606060', 97),
            (7, '미닛메이드오렌지 1.5L', 'drink', '887070707070', 19),
            (8, '스프라이트 500ml', 'drink', '888080808080', 20),
            (9, '포카리스웨트 500ml', 'drink', '889090909090', 27),
            (10, '칠성사이다 1.5L', 'drink', '881212121212', 47)
        ]
        
        # yolo_class_id 컬럼이 없을 경우를 대비해 추가 (Migration)
        try:
            cursor.execute("ALTER TABLE product_master ADD COLUMN yolo_class_id INT AFTER barcode")
            print("✅ product_master 테이블에 yolo_class_id 컬럼 추가 완료.")
        except:
            print("ℹ️ yolo_class_id 컬럼이 이미 존재합니다.")

        cursor.executemany(
            "INSERT INTO product_master (product_id, product_name, category, barcode, yolo_class_id) VALUES (%s, %s, %s, %s, %s)",
            products
        )
        print(f"✅ 신규 상품 {len(products)}종 등록 완료.")

        # 3. 웨이포인트 등록
        cursor.execute(
            "INSERT INTO waypoint (waypoint_id, waypoint_no, waypoint_name, loc_x, loc_y) VALUES (%s, %s, %s, %s, %s)",
            (1, 101, 'Snack-A', 2.0, 1.5)
        )
        print("✅ 웨이포인트(Snack-A) 등록 완료.")

        # 4. 진열 계획 등록 (V2 Schema: barcode_tag directly in plan)
        # 1번 웨이포인트의 1단(row_num=1)에는 1번 상품(신라면)이 있어야 함
        cursor.execute(
            "INSERT INTO waypoint_product_plan (waypoint_id, product_id, barcode_tag, row_num) VALUES (%s, %s, %s, %s)",
            (1, 1, '8801111222233', 1)
        )
        print("✅ 진열 계획(신라면) 등록 완료.")

        # 5. 현재 진행 중인 순찰 회차 생성
        cursor.execute(
            "INSERT INTO patrol_log (patrol_id, start_time, status) VALUES (%s, %s, %s)",
            (1, datetime.now(), '진행중')
        )
        print("✅ 테스트용 순찰 회차(ID: 1) 생성 완료.")

        # 6. 기본 설정 등록
        cursor.execute(
            "INSERT INTO patrol_config (patrol_start_time, patrol_end_time) VALUES (%s, %s)",
            ('09:00:00', '22:00:00')
        )
        print("✅ 시스템 설정 등록 완료.")

        conn.commit()
        print("\n🎉 모든 기초 데이터가 신규 스키마에 맞춰 성공적으로 입력되었습니다!")

    except Exception as e:
        print(f"❌ 데이터 입력 실패: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    insert_base_data()
