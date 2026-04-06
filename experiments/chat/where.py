import os
import time
import sounddevice as sd
import numpy as np
import wave
from google import genai
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

def record_audio(filename="input.wav", duration=5, fs=44100):
    """Records audio for a given duration and saves to a WAV file."""
    print(f"Recording for {duration} seconds...")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()  # Wait until recording is finished
    print("Recording finished.")
    
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(fs)
        wf.writeframes(recording.tobytes())
    return filename

def get_product_from_audio(audio_path):
    """Uploads audio to Gemini and returns the recognized product name."""
    if not client:
        return "None"

    print("Processing audio with Gemini (v2.5 Flash)...")
    
    # In the new SDK, we can upload and generate in one flow or use files.upload
    # For a simple file:
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    # Prompt Gemini to extract the product name
    prompt = "이 녹음 파일에서 사용자가 찾고 있는 '상품명'만 딱 한 단어로 말해줘. 만약 상품명을 찾을 수 없다면 'None'이라고 답변해줘."
    
    # Use the newer model available in the list
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            prompt,
            genai.types.Part.from_bytes(data=audio_data, mime_type="audio/wav")
        ]
    )
    
    product_name = response.text.strip()
    print(f"Recognized Product: {product_name}")
    return product_name

def search_product_location(product_name):
    """Searches the database for the product's location."""
    if not product_name or product_name.lower() == "none":
        return "상품명을 인식하지 못했습니다."

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
        # Using % before and after for fuzzy search
        search_term = f"%{product_name}%"
        cursor.execute(query, (search_term,))
        result = cursor.fetchone()

        if result:
            location = result['waypoint_name'] if result['waypoint_name'] else "위치 정보 없음"
            return f"'{result['product_name']}' 상품은 {location} 위치에 있습니다."
        else:
            return f"'{product_name}' 상품을 데이터베이스에서 찾을 수 없습니다."

    except mysql.connector.Error as err:
        return f"데이터베이스 오류: {err}"
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def main():
    try:
        audio_file = "query.wav"
        record_audio(audio_file)
        
        product_name = get_product_from_audio(audio_file)
        
        result_message = search_product_location(product_name)
        print(f"\n[결과]: {result_message}")

        # Cleanup temporary audio file
        if os.path.exists(audio_file):
            os.remove(audio_file)

    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    main()
