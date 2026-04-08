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
client = genai.Client(api_key=api_key) if api_key else None

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

def get_all_products():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT product_name, category FROM product_master;")
        return cursor.fetchall()
    except: return []
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close(); conn.close()

def identify_product_from_image(image_data):
    if not client: return "None", "API Key Error"
    prompt = """
    이미지에서 상품을 찾아 DB 검색용 명칭을 추출하세요.
    - [PRODUCT_NAME]: 상품 고유 이름 (과자/음료 등 카테고리 단어는 제외)
    - [BOT_RESPONSE]: 고객 안내문 (조사 빼고 간결하게)
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, genai.types.Part.from_bytes(data=image_data, mime_type="image/jpeg")]
        )
        res_text = response.text.strip()
        p_name = "None"; b_resp = "확인 불가"
        for line in res_text.split('\n'):
            if "[PRODUCT_NAME]:" in line: p_name = line.split(":", 1)[1].strip()
            if "[BOT_RESPONSE]:" in line: b_resp = line.split(":", 1)[1].strip()
        return p_name, b_resp
    except Exception as e:
        print(f"Gemini Error: {e}")
        return "None", str(e)

def resolve_fuzzy_product(detected_name, products):
    if not client or not products or detected_name == "None": return detected_name, 0
    inventory_str = ", ".join([p['product_name'] for p in products])
    prompt = f"인식: '{detected_name}'. 실제 목록: [{inventory_str}]. 가장 비슷한 이름 하나만 적고 확신도(%)를 적어. 형식: [MATCH]:이름, [CONFIDENCE]:숫자"
    try:
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        res_text = response.text.strip()
        m_name = detected_name; conf = 0
        for line in res_text.split(','):
            if "[MATCH]:" in line: m_name = line.split(":", 1)[1].strip()
            if "[CONFIDENCE]:" in line:
                try: conf = int("".join(filter(str.isdigit, line)))
                except: conf = 0
        return m_name, conf
    except: return detected_name, 0

def search_product_db(product_name):
    if not product_name or product_name.lower() == "none": return None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM product_master WHERE product_name LIKE %s OR product_name LIKE %s;"
        cursor.execute(query, (f"%{product_name}%", f"{product_name[:2]}%"))
        return cursor.fetchone()
    except: return None
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close(); conn.close()

def draw_text_overlay(frame, text):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (DISPLAY_WIDTH, 60), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    cv2.putText(frame, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

def main():
    print("\n" + "★"*40 + "\nGILBOT VISION (DEBUG MODE)\n" + "★"*40)
    cap = cv2.VideoCapture(os.getenv("RTSP_URL", 0))
    if not cap.isOpened(): print("Cam Error"); return
    
    window_name = "Gilbot"
    img_file = "capture.jpg"

    while True:
        print("\n[Wait] Enter to start (q: quit)")
        if input(">> ").lower() == 'q': break
        
        while True:
            ret, frame = cap.read()
            if not ret: break
            frame = cv2.flip(frame, -1)
            frame = cv2.resize(frame, (800, 480))
            cv2.imshow(window_name, frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '):
                cv2.imwrite(img_file, frame)
                draw_text_overlay(frame, "Analyzing...")
                cv2.imshow(window_name, frame)
                cv2.waitKey(500)
                
                with open(img_file, "rb") as f: data = f.read()
                raw_key, _ = identify_product_from_image(data)
                print(f"🔍 [Debug] Image Analysis: {raw_key}")
                
                # Fuzzy Search
                all_prods = get_all_products()
                suggested, conf = resolve_fuzzy_product(raw_key, all_prods)
                print(f"🔍 [Debug] Fuzzy Match: {suggested} (Conf: {conf}%)")
                
                # DB Search with Fallback
                db_res = search_product_db(suggested if conf >= 80 else raw_key)
                
                if db_res:
                    loc = db_res['waypoint_name'] or "미진열"
                    aisle = loc.split('-')[1] if '-' in loc else loc
                    msg = f"고객님! {db_res['product_name']}. {aisle} 매대에 있습니다."
                else:
                    msg = "죄송합니다. 상품 정보를 확인할 수 없습니다."
                
                draw_text_overlay(frame, msg)
                cv2.imshow(window_name, frame)
                speak_result(msg)
                
                print("[Wait] Space to hide")
                while (cv2.waitKey(1) & 0xFF) != ord(' '):
                    if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1: break
                cv2.destroyAllWindows()
                break
            elif key in [ord('q'), 27]: cv2.destroyAllWindows(); cap.release(); return
    cap.release(); cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
