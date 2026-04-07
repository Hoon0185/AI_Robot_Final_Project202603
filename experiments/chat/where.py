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

# Database Connection Config
DB_CONFIG = {
    'host': os.getenv('LOCAL_DB_HOST', 'localhost'),
    'user': os.getenv('LOCAL_DB_USER', 'gilbot'),
    'password': os.getenv('LOCAL_DB_PASSWORD', 'robot123'),
    'database': os.getenv('LOCAL_DB_NAME', 'gilbot')
}

# --- Configuration ---
# [입력] 카메라에서 직접 음성 수신
RTSP_URL_IN = os.getenv("RTSP_URL", "rtsp://robot1:robot123@192.168.1.18:554/stream1")

# --- Audio/TTS Logic ---
def record_audio(filename="query.wav", duration=5):
    """Records audio from RTSP camera for the specified duration."""
    print(f"\nRecording from RTSP for {duration} seconds... (Listening...)")
    command = [
        "ffmpeg", "-y",
        "-rtsp_transport", "tcp",
        "-i", RTSP_URL_IN,
        "-t", str(duration),
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        "-ac", "1",
        filename
    ]
    try:
        subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"Error during recording: {e.stderr.decode()}")
        return None
    return filename

def speak_result(text):
    """Converts text to speech (FEMALE voice) and plays it through the LOCAL speaker."""
    if not text:
        return
        
    print(f"Generating FEMALE TTS: {text}")
    temp_mp3 = "response.mp3"
    temp_wav = "response.wav"
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
        
        print("🔊 Playing via local speaker (Female Voice)...")
        # PulseAudio first, fall back to ALSA
        if subprocess.run(["which", "paplay"], capture_output=True).returncode == 0:
            subprocess.run(["paplay", temp_wav], check=True)
        else:
            subprocess.run(["aplay", temp_wav], check=True)
            
    except Exception as e:
        print(f"❌ Audio playback error: {e}")
    finally:
        for f in [temp_mp3, temp_wav]:
            if os.path.exists(f):
                os.remove(f)

def get_product_from_audio(audio_path):
    """Uploads audio to Gemini, transcribes it, and extracts intent and product."""
    if not client:
        return "오류: Gemini 클라이언트가 설정되지 않았습니다.", "None", "알 수 없음"

    print("Processing audio with Gemini...")

    with open(audio_path, "rb") as f:
        audio_data = f.read()

    prompt = """당신은 친절한 안내 로봇 '길봇'입니다. 사용자의 요청을 듣고 다음 3가지를 추출해주세요.
    1. 원문(STT): 들리는 그대로의 문장
    2. 상품명: 명시적인 상품 이름 (없으면 None)
    3. 답변 메시지: 로봇이 사용자에게 할 친절한 대답. 
       - 상품 위치를 묻는다면 데이터베이스 검색 결과가 들어갈 자리를 '[LOCATION_RESULT]'라고 표시해줘.
       - 일상 대화(산책, 인사 등)라면 그에 맞는 친절한 대답을 생성해줘.

    응답 형식:
    원문: <전체 문장>
    상품명: <상품명 또는 None>
    답변: <로봇의 대답>"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            prompt,
            genai.types.Part.from_bytes(data=audio_data, mime_type="audio/wav")
        ]
    )

    res_text = response.text.strip()
    
    recognized_text = "인식 실패"
    product_name = "None"
    bot_response = "무슨 말씀인지 잘 모르겠어요."

    for line in res_text.split('\n'):
        if "원문:" in line:
            recognized_text = line.replace("원문:", "").strip()
        elif "상품명:" in line:
            product_name = line.replace("상품명:", "").strip()
        elif "답변:" in line:
            bot_response = line.replace("답변:", "").strip()

    return recognized_text, product_name, bot_response

def search_product_location(product_name):
    """Searches the database for the product's location."""
    if not product_name or product_name.lower() == "none":
        return None

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT pm.product_name, w.waypoint_name
        FROM product_master pm
        LEFT JOIN waypoint_product_plan wpp ON pm.product_id = wpp.product_id
        LEFT JOIN waypoint w ON wpp.waypoint_id = w.waypoint_id
        WHERE pm.product_name LIKE %s;
        """
        search_term = f"%{product_name}%"
        cursor.execute(query, (search_term,))
        result = cursor.fetchone()

        if result:
            location = result['waypoint_name'] if result['waypoint_name'] else "위치 정보 미등록"
            return f"'{result['product_name']}' 상품은 {location} 구역에 마련되어 있습니다."
        else:
            return f"'{product_name}' 상품의 위치 정보를 찾을 수 없습니다."

    except Exception:
        return "데이터베이스 조회 중 오류가 발생했습니다."
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def main():
    print("\n" + "★"*30)
    print("  GILBOT VOICE ASSISTANT (LOCAL AUDIO MODE)")
    print("★"*30)
    
    while True:
        try:
            print("\n📢 대화를 시작하려면 [Enter]를 누르세요. (종료하려면 Ctrl+C)")
            input(">> ")

            audio_file = "query.wav"
            record_audio(audio_file)

            if not os.path.exists(audio_file):
                print("❌ 녹음 파일 생성 실패")
                continue

            recognized_text, product_name, bot_response = get_product_from_audio(audio_file)
            print(f"나: \"{recognized_text}\"")

            if "[LOCATION_RESULT]" in bot_response:
                location_info = search_product_location(product_name)
                if not location_info:
                    location_info = f"'{product_name}' 상품이 무엇인지 잘 모르겠어요."
                bot_response = bot_response.replace("[LOCATION_RESULT]", location_info)

            print(f"길봇: \"{bot_response}\"")
            speak_result(bot_response)

            if os.path.exists(audio_file):
                os.remove(audio_file)

        except KeyboardInterrupt:
            print("\n👋 프로그램을 종료합니다. 감사합니다!")
            break
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
