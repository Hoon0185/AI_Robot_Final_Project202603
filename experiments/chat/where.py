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

    prompt = """
    당신은 친절한 안내 로봇 '길봇'입니다.
    이미지에서 상품을 분석하여 DB 검색을 위한 핵심 명칭을 추출하세요.
    - [PRODUCT_NAME]: 상품 고유 명칭만 추출 (예: '과자 포스틱' -> '포스틱', '음료 코카콜라' -> '코카콜라', '봉지라면 신라면' -> '신라면')
    - [BOT_RESPONSE]: 고객 안내문 (조사 생략, 예: "고객님! [PRODUCT_NAME]. 이 제품은 무엇입니다.")
    경고: '과자', '음료', '라면' 같은 대분류 명칭은 상품명에서 반드시 제외하세요.
    
    ⚠️ 주의사항: 
    - 답변 메시지에 직접적인 구체적인 숫자, 진열대 번호, 구역 명칭을 절대로 기입하지 마십시오. 
    - 위치 정보는 오직 [LOCATION_RESULT] 태그로만 표현해야 합니다. 상상해서 정보를 지어내지 마십시오.

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
    """Searches the database for the product's location and stock status."""
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
        search_term = f"%{product_name}%"
        cursor.execute(query, (search_term,))
        result = cursor.fetchone()

        if result:
            return {
                'name': result['product_name'],
                'location': result['waypoint_name'],
                'stock': result['current_inventory_qty'] if result['current_inventory_qty'] is not None else 0
            }
        else:
            return None

    except Exception as e:
        print(f"❌ DB Error: {e}")
        return None
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
def get_all_products():
    """Fetches all product names and their categories from the database."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT product_name, category FROM product_master;")
        return cursor.fetchall()
    except:
        return []
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close(); conn.close()

def resolve_fuzzy_product(recognized_text, products):
    """Uses Gemini to match an ambiguous user input to the actual inventory."""
    if not client or not products:
        return None, 0
        
    inventory_str = "\n".join([f"- {p['product_name']} ({p['category']})" for p in products])
    
    prompt = f"""
    사용자의 전체 발화: "{recognized_text}"
    우리 매장의 실제 재고 목록 (상품명 및 카테고리):
    {inventory_str}
    
    [미션]
    사용자의 말에는 상품명 오인식(STT 에러)이나 카테고리 힌트(예: 과자, 음료 등)가 섞여 있을 수 있습니다.
    목록 중에서 사용자가 실제로 찾으려고 했을 가능성이 가장 높은 상품을 하나만 골라주세요.
    
    [응답 서식]
    - [MATCH]: 상품명 (정확히 목록에 있는 이름으로, 없으면 None)
    - [CONFIDENCE]: 확신도 % (0~100 숫자만)
    - [REASON]: 판단 근거 (예: "과자 카테고리와 발음의 유사성으로 보아 '포스틱'일 확률 높음")
    """
    
    try:
        response = client.models.generate_content(model="gemini-2.1-flash", contents=prompt)
        res_text = response.text.strip()
        match_name = "None"; confidence = 0
        for line in res_text.split('\n'):
            if "[MATCH]:" in line: match_name = line.split(":", 1)[1].strip()
            if "[CONFIDENCE]:" in line:
                try: confidence = int("".join(filter(str.isdigit, line)))
                except: confidence = 0
        return match_name, confidence
    except:
        return None, 0

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

            # --- [시맨틱 검색 레이어 시작] ---
            # 1단계: 직접 매칭 시도
            res = search_product_location(product_name)
            
            # 2단계: 실패 시 지능형 재분석 시도 (Fuzzy Matching)
            if not res and recognized_text != "인식 실패":
                print("🔍 직접 매칭 실패. 지능형 문맥 분석(Fuzzy Match)을 시작합니다...")
                all_products = get_all_products()
                suggested_name, confidence = resolve_fuzzy_product(recognized_text, all_products)
                
                if suggested_name and suggested_name.lower() != "none" and confidence > 0:
                    if confidence >= 90:
                        print(f"✅ 높은 확신도({confidence}%): '{suggested_name}'(으)로 최종 결정")
                        res = search_product_location(suggested_name)
                    else:
                        print(f"🤔 낮은 확신도({confidence}%): '{suggested_name}' 제안 모드")
                        bot_response = f"고객님! 혹시 {suggested_name} 말씀이신가요? 매장에 그 상품이 있습니다."
            # --- [시맨틱 검색 레이어 끝] ---

            # Final check and Guide Generation
            if res:
                if res['stock'] <= 0:
                    bot_response = f"고객님! {res['name']}. 현재 품절입니다."
                elif not res['location']:
                    bot_response = f"상품이 진열되어 있지 않습니다. 재고가 있으니 카운터에 문의하세요."
                else:
                    raw_loc = res['location']
                    aisle = raw_loc.split('-')[1] if '-' in raw_loc else raw_loc
                    bot_response = f"고객님! {res['name']}. {aisle} 매대에 있습니다."
            elif not res and "[LOCATION_RESULT]" in bot_response:
                bot_response = "죄송합니다. 요청하신 상품의 위치를 찾을 수 없습니다."

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
