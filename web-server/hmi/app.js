document.addEventListener('DOMContentLoaded', () => {
    // 1. Configuration & Discovery
    const API_BASE = '..';
    console.log("HMI initialized. API Base:", API_BASE);

    // 2. Elements Mapping
    const statusIndicator = document.getElementById('status-indicator');
    const posX = document.getElementById('pos-x');
    const posY = document.getElementById('pos-y');
    const currentMode = document.getElementById('current-mode');
    const alertBanner = document.getElementById('alert-banner');
    const alertText = document.getElementById('alert-text');
    const batteryValue = document.getElementById('battery-value');
    const batteryIcon = document.getElementById('battery-icon');
    const btnStart = document.getElementById('btn-start');
    const btnReturn = document.getElementById('btn-return');

    const btnTogglePause = document.getElementById('btn-toggle-pause');
    const btnWhere = document.getElementById('btn-where');
    const btnWhat = document.getElementById('btn-what');
    const videoFeed = document.getElementById('video-feed');
    const videoLoader = document.getElementById('video-loader');

    // Video Loading Handler
    if (videoFeed) {
        videoFeed.onload = () => {
            if (videoLoader) videoLoader.style.display = 'none';
        };
        videoFeed.onerror = () => {
            if (videoLoader) {
                videoLoader.innerHTML = '<i class="fas fa-exclamation-circle"></i> <span>STREAM ERROR</span>';
                videoLoader.style.color = 'var(--danger)';
            }
        };
    }

    // 2.1 Status Translation Map...
    // ... (rest of translation logic is unchanged)
    const STATUS_MAP = {
        "순찰중": "ON PATROL",
        "비상정지": "EMERGENCY STOP",
        "비상정지(중단)": "EMERGENCY",
        "휴식중": "IDLE",
        "대기 중": "IDLE",
        "진행중": "PATROLLING",
        "완료": "FINISHED",
        "중단": "STOPPED",
        "복귀중": "RETURNING HOME"
    };

    const translateState = (koState) => STATUS_MAP[koState] || koState.toUpperCase();

    // 3. Polling Logic...
    const pollStatus = async () => {
        try {
            const response = await fetch(`${API_BASE}/status`);
            if (!response.ok) throw new Error("Network response was not ok");
            const data = await response.json();

            // Update Status Indicator
            if (data.status === "online") {
                statusIndicator.classList.remove('offline');
                statusIndicator.classList.add('online');
                statusIndicator.querySelector('.label').innerText = "ONLINE";
            } else {
                statusIndicator.classList.remove('online');
                statusIndicator.classList.add('offline');
                statusIndicator.querySelector('.label').innerText = "OFFLINE";
            }

            posX.innerText = data.odom_x.toFixed(1);
            posY.innerText = data.odom_y.toFixed(1);
            const bat = data.battery || 0;
            batteryValue.innerText = Math.round(bat);
            
            batteryIcon.className = 'fas';
            if (bat >= 90) batteryIcon.classList.add('fa-battery-full');
            else if (bat >= 60) batteryIcon.classList.add('fa-battery-three-quarters');
            else if (bat >= 40) batteryIcon.classList.add('fa-battery-half');
            else if (bat >= 15) batteryIcon.classList.add('fa-battery-quarter');
            else {
                batteryIcon.classList.add('fa-battery-empty');
                batteryIcon.style.color = '#ff4d4d';
            }
            if (bat >= 15) batteryIcon.style.color = '';

            const koStatus = data.robot_status;
            const enStatus = translateState(koStatus);
            currentMode.innerText = enStatus;

            if (koStatus.includes("정지") || koStatus.includes("STOP") || enStatus.includes("STOP")) {
                btnTogglePause.innerHTML = '<i class="fas fa-undo"></i> RESUME';
                btnTogglePause.className = 'btn btn-success';
            } else {
                btnTogglePause.innerHTML = '<i class="fas fa-stop"></i> STOP';
                btnTogglePause.className = 'btn btn-danger';
            }

            if (enStatus === "ON PATROL" || enStatus === "PATROLLING" || enStatus === "RETURNING HOME") {
                btnStart.disabled = true;
                btnReturn.disabled = (enStatus === "RETURNING HOME");
            } else if (koStatus === "휴식중" || koStatus === "완료" || enStatus === "IDLE" || enStatus === "FINISHED") {
                btnStart.disabled = false;
                btnReturn.disabled = true;
            } else {
                btnStart.disabled = true;
                btnReturn.disabled = false;
            }

        } catch (error) {
            console.error("Status Poll Error:", error);
            statusIndicator.classList.remove('online');
            statusIndicator.classList.add('offline');
            statusIndicator.querySelector('.label').innerText = "ERROR";
        }
    };

    const pollAlerts = async () => {
        try {
            const response = await fetch(`${API_BASE}/robot/alert`);
            if (!response.ok) throw new Error("Network response was not ok");
            const data = await response.json();

            if (data.active) {
                alertBanner.classList.remove('hidden');
                let msg = data.message || "ROBOT ALERT";
                if (msg.includes("우회")) msg = "PATH FINDING...";
                else if (msg.includes("기지에 도착") || msg.includes("복귀 완료")) msg = "MISSION COMPLETE (HOME)";
                alertText.innerText = msg;
            } else {
                alertBanner.classList.add('hidden');
            }
        } catch (error) {
            console.error("Alert Poll Error:", error);
        }
    };

    // 4. Command Handlers
    const sendCommand = async (endpoint, options = {}) => {
        if (!endpoint) return;
        console.log(`Sending command: ${endpoint}`);
        
        // AI 기능의 경우 버튼 비활성화 시각화
        const triggerBtn = options.button;
        if (triggerBtn) {
            triggerBtn.classList.add('processing');
            const originalHTML = triggerBtn.innerHTML;
            triggerBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> PROCESSING...';
            // 텍스트 저장용 클로저
            options.cleanup = () => {
                triggerBtn.classList.remove('processing');
                triggerBtn.innerHTML = originalHTML;
            };
        }

        try {
            const response = await fetch(`${API_BASE}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            
            // AI 응답 영역 업데이트
            const responseArea = document.getElementById('ai-response');
            if (responseArea && data.response) {
                responseArea.innerText = data.response;
            } else if (responseArea && !endpoint.includes('patrol')) {
                // 패트롤 관련 명령이 아닌데 응답이 없는 경우에만 에러 표시 (또는 비움)
                responseArea.innerText = ""; 
            }
            
            if (options.cleanup) options.cleanup();
            return data;
        } catch (error) {
            console.error("Command Error:", error);
            const responseArea = document.getElementById('ai-response');
            if (responseArea) responseArea.innerText = "ERROR: " + error.message;
            if (options.cleanup) options.cleanup();
        }
    };

    const setupButton = (el, getEndpoint, isAI = false) => {
        if (!el) return;
        const handleAction = async (e) => {
            if (el.disabled || el.classList.contains('processing')) return;
            e.preventDefault();
            const endpoint = typeof getEndpoint === 'function' ? getEndpoint() : getEndpoint;
            await sendCommand(endpoint, isAI ? { button: el } : {});
        };
        el.addEventListener('click', handleAction);
        el.addEventListener('touchstart', handleAction, { passive: false });
    };

    setupButton(btnStart, '/patrol/start');
    setupButton(btnReturn, '/patrol/finish');
    setupButton(btnTogglePause, () => {
        const text = btnTogglePause.innerText.trim();
        return text.includes("RESUME") ? '/patrol/resume' : '/patrol/stop';
    });

    // 5. AI Buttons & Video Overlay Setup
    const dashboardMain = document.querySelector('main');
    let videoState = 'inactive'; // 'inactive', 'preview', 'processed'

    setupButton(btnWhere, '/hmi/where', true);

    if (btnWhat) {
        btnWhat.addEventListener('click', async () => {
            dashboardMain.classList.add('video-mode');
            console.log("Video Mode: ON & Triggering Recognition");
            // 영상 모드 진입 시 자동으로 인식 트리거
            await sendCommand('/hmi/what', { button: btnWhat });
        });
    }

    // Video Feed Click Handler (Simple Toggle Off)
    if (videoFeed) {
        videoFeed.addEventListener('click', () => {
            console.log("Video Mode: Returning to Dashboard");
            dashboardMain.classList.remove('video-mode');
        });
    }

    // 6. Intervals
    setInterval(pollStatus, 1000);
    setInterval(pollAlerts, 1000);

    pollStatus();
    pollAlerts();
});
