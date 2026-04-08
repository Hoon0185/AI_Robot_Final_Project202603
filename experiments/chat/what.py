import os
import cv2
import time
import subprocess
import numpy as np
from google import genai
import edge_tts, asyncio
import mysql.connector
from dotenv import load_dotenv

# Load .env for database config (if exists)
load_dotenv()

# Gemini API Configuration
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    client = None
else:
    client = genai.Client(api_key=api_key)

# Database Connection Config
DB_CONFIG = {
    'host': os.getenv('LOCAL_DB_HOST', 'localhost'),
    'user': os.getenv('LOCAL_DB_USER', 'gilbot'),
    'password': os.getenv('LOCAL_DB_PASSWORD', 'robot123'),
    'database': os.getenv('LOCAL_DB_NAME', 'gilbot')
}

# Nextion Resolution
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

# --- Audio/TTS Logic ---
def speak_result(text):
    if not text: return
    print(f"길봇: \"{text}\"")
    temp_mp3 = "response_what.mp3"
    temp_wav = "response_what.wav"
    VOICE = "ko-KR-SunHiNeural"
    try:
        async def _generate():
            communicate = edge_tts.Communicate(text, VOICE)
            await communicate.save(temp_mp3)
        asyncio.run(_generate())
        subprocess.run(["ffmpeg", "-y", "-i", temp_mp3, "-ar", "44100", temp_wav], 
                       check=True, capture_output=True)
        if subprocess.run(["which", "paplay"], capture_output=True).returncode == 0:
            subprocess.run(["paplay", temp_wav], check=True)
        else:
            subprocess.run(["aplay", temp_wav], check=True)
    except Exception as e:
        print(f"Audio Error: {e}")

def identify_product_from_image(image_data):
    if not client: return None, "API Key Error"
    prompt = """
    이미지 속 상품을 분석하여 DB 검색을 위한 핵심 명칭을 추출하세요.
    - [PRODUCT_NAME]: 상품 고유 명칭만 추출 (카테고리 제외) 
      (예: '과자 포스틱' -> '포스틱', '음료 코카콜라' -> '코카콜라', '라면 진라면' -> '진라면')
    - [BOT_RESPONSE]: 고객 안내문 (조사 제거, 예: "고객님! [PRODUCT_NAME]. 이 제품은 무엇입니다.")
    경고: '과자', '음료', '라면' 같은 대분류 명칭은 [PRODUCT_NAME]에서 반드시 제외하세요.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.1-flash",
            contents=[prompt, genai.types.Part.from_bytes(data=image_data, mime_type="image/jpeg")]
        )
        res_text = response.text.strip()
        product_name = "None"; bot_response = "모르겠습니다."
        for line in res_text.split('\n'):
            if "[PRODUCT_NAME]:" in line: product_name = line.split(":", 1)[1].strip()
            if "[BOT_RESPONSE]:" in line: bot_response = line.split(":", 1)[1].strip()
        return product_name, bot_response
    except Exception as e:
        return None, f"Gemini Error: {e}"

def get_all_products():
    """Fetches all product names and their categories from the database."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT product_name, category FROM product_master;")
        return cursor.fetchall()
    except: return []
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close(); conn.close()

def resolve_fuzzy_product(detected_name, products):
    """Refines the detected name using actual inventory context."""
    if not client or not products: return None, 0
    inventory_str = "\n".join([f"- {p['product_name']} ({p['category']})" for p in products])
    prompt = f"""
    시각 인식 결과: "{detected_name}"
    실제 재고 목록:
    {inventory_str}
    
    인식된 이름이 실제 DB 이름과 미세하게 다를 수 있습니다(예: '포테이토칩' -> '포테토칩').
    가장 일치하는 실제 상품명을 골라주세요.
    
    [응답]
    - [MATCH]: 정확한 상품명 (목록에 없으면 None)
    - [CONFIDENCE]: 확신도 %
    """
    try:
        response = client.models.generate_content(model="gemini-2.1-flash", contents=prompt)
        res_text = response.text.strip()
        match_name = detected_name; confidence = 0
        for line in res_text.split('\n'):
            if "[MATCH]:" in line: match_name = line.split(":", 1)[1].strip()
            if "[CONFIDENCE]:" in line:
                try: confidence = int("".join(filter(str.isdigit, line)))
                except: confidence = 0
        return match_name, confidence
    except: return detected_name, 0

def search_product_db(product_name):
    if not product_name or product_name.lower() == "none": return None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        query = "SELECT pm.product_name, pm.current_inventory_qty, w.waypoint_name FROM product_master pm LEFT JOIN waypoint_product_plan wpp ON pm.product_id = wpp.product_id LEFT JOIN waypoint w ON wpp.waypoint_id = w.waypoint_id WHERE pm.product_name LIKE %s;"
        cursor.execute(query, (f"%{product_name}%",))
        return cursor.fetchone()
    except: return None
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close(); conn.close()

def draw_text_overlay(frame, text):
    """Draws a nice semi-transparent overlay with text."""
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (DISPLAY_WIDTH, 60), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(frame, text, (20, 40), font, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

def get_camera():
    RTSP_URL = os.getenv("RTSP_URL", "rtsp://robot1:robot123@192.168.1.18:554/stream1")
    for source in [RTSP_URL, 0, 1, 2]:
        cap = cv2.VideoCapture(source)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret: return cap
            cap.release()
    return None

def main():
    print("\n" + "★"*40)
    print("  GILBOT NEXTION VISION (INTELLIGENT MODE)")
    print("★"*40)
    
    cap = get_camera()
    if not cap:
        print("Camera Error."); return

    window_name = "Gilbot Vision (800x480)"
    img_file = "capture.jpg"

    while True:
        print("\n[대기 중] [Enter]를 누르세요. (종료: q)")
        key_input = input(">> ")
        if key_input.lower() == 'q': break

        print("카메라를 켭니다. [Space]를 눌러 분석하세요.")
        while True:
            ret, frame = cap.read()
            if not ret: break
            frame = cv2.flip(frame, -1)
            frame = cv2.resize(frame, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
            cv2.imshow(window_name, frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '): 
                cv2.imwrite(img_file, frame)
                draw_text_overlay(frame, "Analyzing...")
                cv2.imshow(window_name, frame)
                cv2.waitKey(1)
                
                with open(img_file, "rb") as f: image_data = f.read()
                prod_key_raw, bot_text = identify_product_from_image(image_data)
                
                # Semantic Refinement
                all_prods = get_all_products()
                prod_key, confidence = resolve_fuzzy_product(prod_key_raw, all_prods)
                if confidence >= 90: prod_key = prod_key
                else: prod_key = prod_key_raw # Fallback or Suggest

                # DB Context Guide
                db_res = search_product_db(prod_key)
                if db_res:
                    raw_loc = db_res['waypoint_name'] if db_res['waypoint_name'] else "미진열"
                    aisle = raw_loc.split('-')[1] if '-' in raw_loc else raw_loc
                    stock = db_res['current_inventory_qty']
                    if stock <= 0:
                        final_msg = f"고객님! {db_res['product_name']}. 현재 품절입니다."
                    else:
                        final_msg = f"고객님! {db_res['product_name']}. {aisle} 매대에 있습니다."
                else:
                    final_msg = f"고객님! {prod_key}. 상품을 찾을 수 없어요."

                print(f"결과: {final_msg}")
                draw_text_overlay(frame, final_msg)
                cv2.imshow(window_name, frame)
                speak_result(final_msg)
                
                print("[Space]를 눌러 창을 닫으세요.")
                while True:
                    key_inner = cv2.waitKey(1) & 0xFF
                    if key_inner == ord(' '): break
                    if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1: break
                cv2.destroyAllWindows()
                break 

            elif key == ord('q') or key == 27:
                cv2.destroyAllWindows()
                cap.release(); return
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
