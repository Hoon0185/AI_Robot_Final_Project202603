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
    사진 속 정면에 보이는 상품을 분석하여 다음 형식으로 답변하세요.
    - [PRODUCT_NAME]: 상품명 (DB 검색용 한 단어)
    - [BOT_RESPONSE]: 고객에게 말할 친절한 안내 (예: "고객님, [PRODUCT_NAME]. 이 제품은 무엇입니다.")
    경고: 절대 은(는) 같은 조사를 사족으로 달지 마세요.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
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
    print("  GILBOT NEXTION VISION ASSISTANT (CAMERA FLIPPED)")
    print("★"*40)
    
    cap = get_camera()
    if not cap:
        print("Camera Error."); return

    window_name = "Gilbot Vision (800x480)"
    img_file = "capture.jpg"

    while True:
        # STEP 1: HIDDEN 
        print("\n[대기 중] 눈앞의 사물을 확인하려면 [Enter]를 누르세요. (종료: q)")
        key_input = input(">> ")
        if key_input.lower() == 'q': break

        # STEP 2: PREVIEW 
        print("카메라를 켭니다. [Space]를 눌러 분석하세요.")
        while True:
            ret, frame = cap.read()
            if not ret: break
            
            # Flip 180 deg for upside-down camera mount
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
                prod_key, bot_text = identify_product_from_image(image_data)
                
                # FACT CHECK with DB
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
                    # Clean up Gemini's response (remove 은/는 if present)
                    clean_bot = bot_text.replace("은(는) ", " ").replace("은 ", " ").replace("는 ", " ")
                    final_msg = clean_bot if prod_key != "None" else "상품을 찾을 수 없습니다."

                # STEP 3: RESULT 
                print(f"결과: {final_msg}")
                draw_text_overlay(frame, final_msg)
                cv2.imshow(window_name, frame)
                speak_result(final_msg)
                
                print("안내를 마치려면 [Space]를 누르세요.")
                while True:
                    key_inner = cv2.waitKey(1) & 0xFF
                    if key_inner == ord(' '): break
                    if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1: break
                
                cv2.destroyAllWindows()
                break 

            elif key == ord('q') or key == 27:
                cv2.destroyAllWindows()
                cap.release()
                return

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
