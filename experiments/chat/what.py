import os
import cv2
import time
import subprocess
from google import genai
import edge_tts, asyncio
import mysql.connector
from dotenv import load_dotenv

# Load .env for database config (if exists)
load_dotenv()

# Gemini API Configuration
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Warning: GEMINI_API_KEY not found in environment.")
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

# --- Audio/TTS Logic ---
def speak_result(text):
    """Converts text to speech (FEMALE voice) and plays it through the LOCAL speaker."""
    if not text:
        return
        
    print(f"길봇: \"{text}\"")
    temp_mp3 = "response_what.mp3"
    temp_wav = "response_what.wav"
    VOICE = "ko-KR-SunHiNeural"
    
    try:
        # Create TTS asynchronously using edge-tts
        async def _generate():
            communicate = edge_tts.Communicate(text, VOICE)
            await communicate.save(temp_mp3)
        
        asyncio.run(_generate())
        
        # Convert to WAV for local players
        subprocess.run(["ffmpeg", "-y", "-i", temp_mp3, "-ar", "44100", temp_wav], 
                       check=True, capture_output=True)
        
        # PulseAudio first, fall back to ALSA
        if subprocess.run(["which", "paplay"], capture_output=True).returncode == 0:
            subprocess.run(["paplay", temp_wav], check=True)
        else:
            subprocess.run(["aplay", temp_wav], check=True)
            
    except Exception as e:
        print(f"Error during audio output: {e}")

def identify_product_from_image(image_path):
    """Uploads image to Gemini and returns recognized info."""
    if not client:
        return None, "API 키가 설정되지 않았습니다."

    # Prompt Gemini to extract product name and a polite response
    prompt = """
    사진 속 정면에 보이는 상품을 분석하여 다음 형식으로 답변하세요.
    - [PRODUCT_NAME]: 상품명 (DB 검색용, 가장 핵심적인 브랜드/제품 명칭 한 단어)
    - [BOT_RESPONSE]: 고객에게 직접 말할 한 문장 이내의 아주 짧고 친절한 인사/안내 (예: "고객님, 이 제품은 [PRODUCT_NAME]입니다.")

    ⚠️ 주의: 
    - 상품명을 찾을 수 없다면 [PRODUCT_NAME]에 'None'이라고 적으세요.
    - [BOT_RESPONSE]에는 절대 구체적인 위치(진열대 번호 등)를 지어내서 쓰지 마십시오.
    """

    with open(image_path, "rb") as f:
        image_data = f.read()

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                prompt,
                genai.types.Part.from_bytes(data=image_data, mime_type="image/jpeg")
            ]
        )

        res_text = response.text.strip()
        product_name = "None"
        bot_response = "무엇인지 잘 모르겠습니다."

        for line in res_text.split('\n'):
            if "[PRODUCT_NAME]:" in line:
                product_name = line.split(":", 1)[1].strip()
            if "[BOT_RESPONSE]:" in line:
                bot_response = line.split(":", 1)[1].strip()

        return product_name, bot_response
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return None, "분석 중 오류가 발생했습니다."

def search_product_db(product_name):
    """Searches the database for product details."""
    if not product_name or product_name.lower() == "none":
        return None

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT pm.product_name, pm.current_inventory_qty, w.waypoint_name
        FROM product_master pm
        LEFT JOIN waypoint_product_plan wpp ON pm.product_id = wpp.product_id
        LEFT JOIN waypoint w ON wpp.waypoint_id = w.waypoint_id
        WHERE pm.product_name LIKE %s;
        """
        cursor.execute(query, (f"%{product_name}%",))
        result = cursor.fetchone()
        return result
    except Exception as e:
        print(f"DB Error: {e}")
        return None
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def main():
    print("\n" + "★"*40)
    print("  GILBOT VISION ASSISTANT (WHAT IS THIS?)")
    print("★"*40)
    
    cap = cv2.VideoCapture(0) # Default to first camera
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    window_name = "Gilbot Vision - [Space] to Analyze, [q] to Quit"
    img_file = "capture.jpg"

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord(' '): # Capture & Process
                print("\nCapturing and analyzing...")
                cv2.imwrite(img_file, frame)
                
                prod_key, bot_text = identify_product_from_image(img_file)
                
                # FACT CHECK with DB
                db_res = search_product_db(prod_key)
                if db_res:
                    loc = db_res['waypoint_name'] if db_res['waypoint_name'] else "미진열 상태"
                    stock = db_res['current_inventory_qty']
                    
                    if stock <= 0:
                        final_msg = f"고객님! 상품 {db_res['product_name']}은(는) 현재 품절입니다."
                    else:
                        final_msg = f"고객님! 상품 {db_res['product_name']}은(는) {loc}에 있습니다."
                else:
                    final_msg = bot_text if prod_key != "None" else "죄송합니다. 상품 정보를 찾을 수 없습니다."

                speak_result(final_msg)
                print("Ready for next capture.")

            elif key == ord('q') or key == 27:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Vision Assistant closed.")

if __name__ == "__main__":
    main()
