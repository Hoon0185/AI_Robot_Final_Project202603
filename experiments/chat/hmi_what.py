import os
import cv2
import time
import subprocess
from google import genai
from PIL import Image
import edge_tts, asyncio
from dotenv import load_dotenv

load_dotenv()

# Gemini API Configuration
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    # Just in case, try to load from other common locations if .env failed
    print("Warning: GEMINI_API_KEY not found in environment.")
    client = None
else:
    client = genai.Client(api_key=api_key)

# --- Configuration ---
RTSP_URL = os.getenv("RTSP_URL", "rtsp://robot1:robot123@192.168.1.18:554/stream1")

def speak_result(text):
    """Converts text to speech and plays it through the LOCAL PC speaker."""
    if not text: return
    print(f"Bot: {text}")
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
        print(f"Audio error: {e}")
    finally:
        for f in [temp_mp3, temp_wav]:
            if os.path.exists(f): os.remove(f)

def capture_frame(filename="capture_hmi.jpg"):
    """Tries multiple sources to capture a single frame."""
    sources = [RTSP_URL, 0, 1, 2, 3]
    for src in sources:
        print(f"Attempting source: {src}")
        cap = cv2.VideoCapture(src)
        if cap.isOpened():
            # Skip frames to clear buffer if it's RTSP
            if isinstance(src, str) and src.startswith("rtsp"):
                for _ in range(5): cap.grab()
            ret, frame = cap.read()
            cap.release()
            if ret:
                cv2.imwrite(filename, frame)
                print(f"Successfully captured to {filename}")
                return filename
    return None

def analyze_image(image_path):
    if not client: return "알려드릴 수 없습니다. (API Key 없음)"
    img = Image.open(image_path)
    prompt = """
    당신은 친절한 안내 로봇 '길봇'입니다.
    이미지 속의 상품을 분석하여 다음과 같이 질문에 답하세요.
    1. 상품명: <상품명>
    2. 로봇의 대답: <정말 친절하고 상냥하게, '고객님, 이 제품은 ~입니다'라고 답변하세요>
    3. 상품이 보이지 않으면 '상품을 찾을 수 없습니다'라고 말씀하세요."""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, img]
        )
        res_text = response.text.strip()
        bot_response = "무슨 상품인지 잘 모르겠어요."
        for line in res_text.split('\n'):
            if "로봇의 대답:" in line or "2. 로봇의 대답:" in line:
                bot_response = line.split("대답:")[1].strip()
        return bot_response
    except Exception as e:
        print(f"Analysis Error: {e}")
        return "죄송합니다. 분석 중에 오류가 발생했습니다."

def run_hmi_what():
    img_file = capture_frame()
    if not img_file:
        resp = "카메라를 연결할 수 없습니다."
        speak_result(resp)
        return resp
    
    resp = analyze_image(img_file)
    speak_result(resp)
    if os.path.exists(img_file): os.remove(img_file)
    return resp

if __name__ == "__main__":
    print(run_hmi_what())
