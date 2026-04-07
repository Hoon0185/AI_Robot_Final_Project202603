import sys
import subprocess
import os
from gtts import gTTS
from onvif import ONVIFCamera

# --- Configuration (Tapo C100) ---
CAM_IP = '192.168.1.18'
CAM_PORT = 2020
CAM_USER = 'robot1'
CAM_PASS = 'robot123'
WSDL_PATH = '/home/robot/.local/lib/python3.10/site-packages/onvif/wsdl/'

def get_backchannel_url():
    """Authenticates via ONVIF and requests a specialized RTSP URL for audio output."""
    try:
        print(f"Connecting to ONVIF at {CAM_IP}:{CAM_PORT}...")
        cam = ONVIFCamera(CAM_IP, CAM_PORT, CAM_USER, CAM_PASS, WSDL_PATH)
        media = cam.create_media_service()
        profiles = media.GetProfiles()
        
        if not profiles:
            print("No ONVIF profiles found.")
            return None
            
        token = profiles[0].token
        print(f"Found ONVIF profile token: {token}")
        
        # Create StreamSetup for RTSP Backchannel
        obj = media.create_type('GetStreamUri')
        obj.ProfileToken = token
        obj.StreamSetup = {
            'Stream': 'RTP-Unicast',
            'Transport': {'Protocol': 'RTSP'}
        }
        
        # Request the specialized URI
        uri_obj = media.GetStreamUri(obj)
        # Inject credentials into the URI if not present
        uri = uri_obj.Uri
        if "://" in uri and f"{CAM_USER}:" not in uri:
            uri = uri.replace("://", f"://{CAM_USER}:{CAM_PASS}@")
        
        return uri
    except Exception as e:
        print(f"ONVIF Authentication Error: {e}")
        # Fallback to direct URL if ONVIF fails
        return f"rtsp://{CAM_USER}:{CAM_PASS}@{CAM_IP}:554/stream1?backchannel=1"

def speak(text, volume="12.0"):
    """Main speaker function: Handshake + TTS + Stream."""
    print(f"\n[안내 송출 시작]: {text}")
    
    # 1. Get Secure URL
    target_url = get_backchannel_url()
    print(f"Secure Target URL: {target_url}")
    
    # 2. Generate TTS
    tts = gTTS(text=text, lang='ko')
    filename = "temp_voice.mp3"
    tts.save(filename)
    
    # 3. Stream via ffmpeg with aggressive volume boost
    command = [
        "ffmpeg", "-re", "-y",
        "-i", filename,
        "-af", f"volume={volume}",
        "-f", "rtsp",
        "-rtsp_transport", "tcp",
        "-vn", 
        "-acodec", "pcm_alaw",  # Tapo usually prefers PCMA
        "-ar", "8000",
        "-ac", "1",
        target_url
    ]
    
    try:
        print("Pushing audio stream to camera...")
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
        print("✅ 오디오 안내 완료!")
    except subprocess.TimeoutExpired:
        print("✅ 오디오 안내 전송 완료 (타임아웃)")
    except subprocess.CalledProcessError as e:
        print(f"❌ 송출 실패: {e.stderr}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    test_msg = sys.argv[1] if len(sys.argv) > 1 else "보안 핸드셰이크를 통한 타포 카메라 테스트 방송입니다. 소리가 잘 들리시나요?"
    speak(test_msg)
