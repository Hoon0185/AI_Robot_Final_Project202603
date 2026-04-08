import os
import time
import subprocess
import wave
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

# Database Connection Config (Consolidated to use REMOTE by default as per previous task)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '16.184.56.119'),
    'user': os.getenv('DB_USER', 'gilbot'),
    'password': os.getenv('DB_PASSWORD', 'robot123'),
    'database': os.getenv('DB_NAME', 'gilbot')
}

# --- Configuration ---
RTSP_URL_IN = os.getenv("RTSP_URL", "rtsp://robot1:robot123@192.168.1.18:554/stream1")

# --- Audio/TTS Logic ---
def record_audio(filename="query_hmi.wav", duration=5):
    """Records audio from RTSP camera for the specified duration."""
    # Internal logging to stderr to keep stdout clean for the API
    import sys
    sys.stderr.write(f"Recording from RTSP for {duration} seconds...\n")
    
    command = [
        "ffmpeg", "-y",
        "-stimeout", "3000000",   # 3 seconds connection timeout
        "-rtsp_transport", "tcp",
        "-analyzeduration", "0",  # Faster startup
        "-probesize", "32",       # Faster startup
        "-i", RTSP_URL_IN,
        "-t", str(duration),      # Strict 5 seconds
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        "-ac", "1",
        filename
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=12)
    except Exception as e:
        sys.stderr.write(f"Error during recording: {e}\n")
        return None
    return filename

def speak_result(text):
    """Converts text to speech and plays it through the LOCAL PC speaker."""
    if not text: return
    import sys
    sys.stderr.write(f"Bot: {text}\n")
    temp_mp3 = "response_hmi.mp3"
    temp_wav = "response_hmi.wav"
    VOICE = "ko-KR-SunHiNeural"
    try:
        async def _generate():
            communicate = edge_tts.Communicate(text, VOICE)
            await communicate.save(temp_mp3)
        asyncio.run(_generate())
        subprocess.run(["ffmpeg", "-y", "-i", temp_mp3, "-ar", "44100", temp_wav], 
                       check=True, capture_output=True, timeout=5)
        if subprocess.run(["which", "paplay"], capture_output=True).returncode == 0:
            subprocess.run(["paplay", temp_wav], check=True, timeout=10)
        else:
            subprocess.run(["aplay", temp_wav], check=True, timeout=10)
    except Exception as e:
        sys.stderr.write(f"Audio error: {e}\n")
    finally:
        for f in [temp_mp3, temp_wav]:
            if os.path.exists(f): os.remove(f)

def get_product_from_audio(audio_path):
    if not client: return "오류", "None", "Gemini API Error"
    with open(audio_path, "rb") as f: data = f.read()
    prompt = """
    당신은 친절한 안내 로봇 '길봇'입니다.
    이미지에서 상품을 분석하여 DB 검색을 위한 핵심 명칭을 추출하세요.
    - [PRODUCT_NAME]: 상품 고유 명칭만 추출
    - [BOT_RESPONSE]: 고객 안내문
    응답 형식:
    원문: <전체 문장>
    상품명: <상품명 또는 None>
    답변: <로봇의 대답>"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, genai.types.Part.from_bytes(data=data, mime_type="audio/wav")]
        )
        res_text = response.text.strip()
        recognized_text = "인식 실패"; product_name = "None"; bot_response = "잘 모르겠어요."
        for line in res_text.split('\n'):
            if "원문:" in line: recognized_text = line.replace("원문:", "").strip()
            elif "상품명:" in line: product_name = line.replace("상품명:", "").strip()
            elif "답변:" in line: bot_response = line.replace("답변:", "").strip()
        return recognized_text, product_name, bot_response
    except: return "에러", "None", "처리 실패"

def search_product_location(product_name):
    if not product_name or product_name.lower() == "none": return None
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
        return cursor.fetchone()
    except: return None
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close(); conn.close()

def run_hmi_where():
    import sys
    audio_file = "query_hmi.wav"
    record_audio(audio_file)
    if not os.path.exists(audio_file): return "녹음에 실패했습니다. 카메라 연결을 확인해주세요."

    rec_text, prod_name, bot_resp = get_product_from_audio(audio_file)
    sys.stderr.write(f"User: {rec_text}\n")

    res = search_product_location(prod_name)
    if res:
        if res['current_inventory_qty'] <= 0:
            bot_resp = f"고객님! {res['product_name']}. 현재 품절입니다."
        else:
            loc = res['waypoint_name'] or "미진열"
            aisle = loc.split('-')[1] if '-' in loc else loc
            bot_resp = f"고객님! {res['product_name']}. {aisle} 매대에 있습니다."
    
    speak_result(bot_resp)
    if os.path.exists(audio_file): os.remove(audio_file)
    return bot_resp

if __name__ == "__main__":
    print(run_hmi_where())
