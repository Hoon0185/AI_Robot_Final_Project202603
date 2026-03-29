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
            'host': os.getenv('DB_HOST', '127.0.0.1'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'gilbot'),
            'password': os.getenv('DB_PASSWORD', 'robot123'),
            'database': os.getenv('DB_NAME', 'gilbot')
        }

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        print("--- Gilbot 기초 데이터 입력 시작 ---")

        # 1. 외래 키 체크 해제 및 기존 데이터 정리 (순서 중요)
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        tables = [
            'alert', 'detection_log', 'shelf_status', 
            'waypoint_product_plan', 'slot', 'waypoint', 
            'product_master', 'patrol_log', 'patrol_config'
        ]
        for table in tables:
            cursor.execute(f"TRUNCATE TABLE {table}")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        print("✅ 기존 테이블 데이터 초기화 완료.")

        # 2. 상품 마스터 등록
        products = [
            (1, '신라면', 'snack', '8801111222233'),
            (2, '초코에몽', 'drink', '8801111999999'),
            (3, '불닭볶음면', 'snack', '8801111555555')
        ]
        cursor.executemany(
            "INSERT INTO product_master (product_id, product_name, category, barcode) VALUES (%s, %s, %s, %s)",
            products
        )
        print(f"✅ 상품 {len(products)}종 등록 완료.")

        # 3. 웨이포인트 등록
        cursor.execute(
            "INSERT INTO waypoint (waypoint_id, waypoint_no, waypoint_name, loc_x, loc_y) VALUES (%s, %s, %s, %s, %s)",
            (1, 101, 'Snack-A', 2.0, 1.5)
        )
        print("✅ 웨이포인트(Snack-A) 등록 완료.")

        # 4. 슬롯 등록 (태그 바코드를 8801111222233으로 설정)
        cursor.execute(
            "INSERT INTO slot (slot_id, waypoint_id, row_num, barcode_tag) VALUES (%s, %s, %s, %s)",
            (1, 1, 1, '8801111222233')
        )
        print("✅ 매대 슬롯(태그: 8801111222233) 등록 완료.")

        # 5. 진열 계획 등록 (1번 슬롯에는 반드시 1번 상품(신라면)이 있어야 함)
        cursor.execute(
            "INSERT INTO waypoint_product_plan (waypoint_id, slot_id, product_id) VALUES (%s, %s, %s)",
            (1, 1, 1)
        )
        print("✅ 진열 계획(신라면) 등록 완료.")

        # 6. 현재 진행 중인 순찰 회차 생성
        cursor.execute(
            "INSERT INTO patrol_log (patrol_id, start_time, status) VALUES (%s, %s, %s)",
            (1, datetime.now(), '진행중')
        )
        print("✅ 테스트용 순찰 회차(ID: 1) 생성 완료.")

        # 7. 기본 설정 등록
        cursor.execute(
            "INSERT INTO patrol_config (patrol_start_time, patrol_end_time) VALUES (%s, %s)",
            ('09:00:00', '22:00:00')
        )
        print("✅ 시스템 설정 등록 완료.")

        conn.commit()
        print("\n🎉 모든 기초 데이터가 성공적으로 입력되었습니다!")
        print("이제 'python3 simulate_robot.py'를 실행하여 테스트할 수 있습니다.")

    except Exception as e:
        print(f"❌ 데이터 입력 실패: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    insert_base_data()
