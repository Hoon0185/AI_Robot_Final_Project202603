import mysql.connector
from mysql.connector import Error
import sys
import os

# DB 설정
DB_CONFIG = {
    "host": "localhost",
    "user": "gilbot",
    "password": "robot123",
    "database": "gilbot"
}

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"❌ DB 연결 오류: {e}")
        return None

def list_products(cursor):
    cursor.execute("SELECT product_id, product_name, barcode, min_inventory_qty, current_inventory_qty, is_alert_resolved FROM product_master")
    products = cursor.fetchall()
    
    print("\n" + "="*80)
    print(f"{'ID':<4} | {'상품명':<20} | {'바코드':<15} | {'재고':<6} | {'최소':<6} | {'상태'}")
    print("-" * 80)
    
    for p in products:
        pid, name, bc, min_qty, curr_qty, resolved = p
        status = "✅ 정상"
        if curr_qty < min_qty:
            status = "🚨 부족" if not resolved else "⚠️ 확인필요"
            
        print(f"{pid:<4} | {name:<20} | {bc:<15} | {curr_qty:<6} | {min_qty:<6} | {status}")
    print("=" * 80)
    return products

def update_inventory(conn, product_id, change_qty, mode='in'):
    cursor = conn.cursor(dictionary=True)
    
    # 현재 정보 조회
    cursor.execute("SELECT product_name, current_inventory_qty, min_inventory_qty FROM product_master WHERE product_id = %s", (product_id,))
    product = cursor.fetchone()
    
    if not product:
        print("❌ 해당 ID의 상품을 찾을 수 없습니다.")
        return

    curr_qty = product['current_inventory_qty']
    min_qty = product['min_inventory_qty']
    
    if mode == 'in':
        new_qty = curr_qty + change_qty
    else:
        if curr_qty < change_qty:
            print(f"❌ 재고 부족! (현재: {curr_qty}, 출고 요청: {change_qty})")
            return
        new_qty = curr_qty - change_qty

    # 알림 로직
    alert_log = None
    is_alert_resolved = 1 # 기본은 해결 상태 (또는 정상)
    
    if new_qty < min_qty:
        alert_log = f"재고 부족: 현재 {new_qty}개 (최소 {min_qty}개 필요)"
        is_alert_resolved = 0
        print(f"\n⚠️ 경고: {product['product_name']}의 재고가 최소 수량 미만으로 떨어집니다!")

    # DB 업데이트
    update_sql = """
        UPDATE product_master 
        SET current_inventory_qty = %s, 
            alert_log = %s, 
            is_alert_resolved = %s 
        WHERE product_id = %s
    """
    cursor.execute(update_sql, (new_qty, alert_log, is_alert_resolved, product_id))
    conn.commit()
    
    print(f"\n✅ {product['product_name']} 업데이트 완료: {curr_qty} -> {new_qty}")

def main():
    conn = get_db_connection()
    if not conn:
        return

    while True:
        try:
            cursor = conn.cursor()
            products = list_products(cursor)
            
            print("\n[메뉴] 1:입고(+) 2:출고(-) q:종료")
            choice = input("선택: ").strip().lower()
            
            if choice == 'q':
                print("프로그램을 종료합니다.")
                break
            
            if choice not in ['1', '2']:
                print("❌ 잘못된 선택입니다.")
                continue
            
            pid = input("상품 ID: ").strip()
            if not pid.isdigit():
                print("❌ 숫자로 된 ID를 입력하세요.")
                continue
            
            qty_str = input("수량: ").strip()
            if not qty_str.isdigit():
                print("❌ 숫자로 된 수량을 입력하세요.")
                continue
            
            qty = int(qty_str)
            mode = 'in' if choice == '1' else 'out'
            
            update_inventory(conn, int(pid), qty, mode)
            input("\n계속하려면 엔터를 누르세요...")
            clear_screen()
            
        except KeyboardInterrupt:
            print("\n종료합니다.")
            break
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            input("엔터를 누르세요...")

    if conn.is_connected():
        conn.close()

if __name__ == "__main__":
    main()
