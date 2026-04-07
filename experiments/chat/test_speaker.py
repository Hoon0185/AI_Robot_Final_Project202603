import subprocess
import os
from gtts import gTTS

# --- Configuration (Tapo C100 via go2rtc bridge) ---
RTSP_URL_OUT = "rtsp://localhost:8554/tapo_bridge"
AUDIO_CODEC = "pcm_mulaw"
SAMPLE_RATE = "8000"
VOLUME_BOOST = "10.0" # 테스트를 위해 10배로 설정

def test_speak(text):
    print(f"\n[테스트 송출 시작]: {text}")
    
    # 1. TTS 생성
    tts = gTTS(text=text, lang='ko')
    filename = "test_voice.mp3"
    tts.save(filename)
    
    # 2. ffmpeg 송출 (go2rtc 브릿지 대상)
    command = [
        "ffmpeg", "-re", "-y",
        "-i", filename,
        "-af", f"volume={VOLUME_BOOST}",
        "-f", "rtsp",
        "-rtsp_transport", "tcp",
        "-vn", 
        "-acodec", AUDIO_CODEC,
        "-ar", SAMPLE_RATE,
        "-ac", "1",
        RTSP_URL_OUT
    ]
    
    try:
        print(f"Sending to {RTSP_URL_OUT}...")
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=15)
        print("✅ 테스트 송출 성공!")
    except subprocess.TimeoutExpired:
        print("✅ 송출 완료 (타임아웃으로 자동 종료)")
    except subprocess.CalledProcessError as e:
        print(f"❌ 송출 실패: {e.stderr}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    message = "안녕하세요. 이것은 타포 카메라 스피커 테스트 방송입니다. 소리가 잘 들리시나요? 볼륨을 십 배로 높여서 전송 중입니다."
    test_speak(message)
