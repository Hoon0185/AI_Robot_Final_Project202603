import sys
import os
import subprocess
from gtts import gTTS

def speak_direct(text):
    # 1. TTS 생성
    tts = gTTS(text=text, lang='ko')
    tts.save("/tmp/speak.mp3")
    
    # 2. Tapo 최적화 규격으로 변환 (PCM ALAW, 8000Hz, Mono, 50배 증폭)
    subprocess.run([
        "ffmpeg", "-y", "-i", "/tmp/speak.mp3",
        "-af", "volume=50.0",
        "-acodec", "pcm_alaw", "-ar", "8000", "-ac", "1",
        "/tmp/speak.wav"
    ], check=True)
    
    # 3. 정식 RTSP 백채널 송출 (가장 표준적인 경로)
    # go2rtc를 거치지 않고 직접 카메라의 백채널로 꽂습니다.
    # Tapo C100의 경우 stream1에서도 오디오 수신권을 부여받아야 합니다.
    url = "rtsp://robot1:robot123@192.168.1.18:554/stream1"
    
    command = [
        "ffmpeg", "-re", "-y", "-i", "/tmp/speak.wav",
        "-f", "rtsp", "-rtsp_transport", "tcp",
        url
    ]
    
    print(f"Direct pushing to {url}...")
    subprocess.run(command)

if __name__ == '__main__':
    msg = sys.argv[1] if len(sys.argv) > 1 else "최종 보안 우회 테스트 방송입니다."
    speak_direct(msg)
