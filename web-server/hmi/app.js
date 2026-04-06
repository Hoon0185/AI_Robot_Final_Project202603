document.addEventListener('DOMContentLoaded', () => {
    // 1. Configuration & Discovery
    const API_BASE = window.location.origin + "/api";
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

    const btnTogglePause = document.getElementById('btn-toggle-pause');

    // 2.1 Status Translation Map (To avoid Korean font issues on robot hardware)
    const STATUS_MAP = {
        "순찰중": "ON PATROL",
        "비상정지": "EMERGENCY STOP",
        "비상정지(중단)": "EMERGENCY",
        "휴식중": "IDLE",
        "대기 중": "IDLE",
        "진행중": "PATROLLING",
        "완료": "FINISHED",
        "중단": "STOPPED"
    };

    const translateState = (koState) => STATUS_MAP[koState] || koState.toUpperCase();

    // 3. Polling Logic
    const pollStatus = async () => {
        try {
            const response = await fetch(`${API_BASE}/status`);
            if (!response.ok) throw new Error("Network response was not ok");
            const data = await response.json();

            // Update Status Indicator (ONLINE/OFFLINE)
            if (data.status === "online") {
                statusIndicator.classList.remove('offline');
                statusIndicator.classList.add('online');
                statusIndicator.querySelector('.label').innerText = "ONLINE";
            } else {
                statusIndicator.classList.remove('online');
                statusIndicator.classList.add('offline');
                statusIndicator.querySelector('.label').innerText = "OFFLINE";
            }

            // Update Positioning
            posX.innerText = data.odom_x.toFixed(1);
            posY.innerText = data.odom_y.toFixed(1);

            // Update Battery
            const bat = data.battery || 0;
            batteryValue.innerText = Math.round(bat);
            
            // Battery Icon Update
            batteryIcon.className = 'fas'; // Base class
            if (bat >= 90) batteryIcon.classList.add('fa-battery-full');
            else if (bat >= 60) batteryIcon.classList.add('fa-battery-three-quarters');
            else if (bat >= 40) batteryIcon.classList.add('fa-battery-half');
            else if (bat >= 15) batteryIcon.classList.add('fa-battery-quarter');
            else {
                batteryIcon.classList.add('fa-battery-empty');
                batteryIcon.style.color = '#ff4d4d'; // Red alert for low battery
            }
            if (bat >= 15) batteryIcon.style.color = ''; // Reset color if not empty

            // Update Mode & Toggle Button UI (English Only)
            const koStatus = data.robot_status;
            const enStatus = translateState(koStatus);
            currentMode.innerText = enStatus;

            // Toggle Button Logic: If stopped, show RESUME. Else, show STOP.
            if (koStatus.includes("정지") || koStatus.includes("STOP") || enStatus.includes("STOP")) {
                btnTogglePause.innerHTML = '<i class="fas fa-undo"></i> RESUME';
                btnTogglePause.className = 'btn btn-success';
                btnTogglePause.onclick = () => sendCommand('/patrol/resume');
            } else {
                btnTogglePause.innerHTML = '<i class="fas fa-stop"></i> STOP';
                btnTogglePause.className = 'btn btn-danger';
                btnTogglePause.onclick = () => sendCommand('/patrol/stop');
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
                // Force English for alerts to avoid tofu characters
                alertText.innerText = (data.message && data.message.includes("우회")) ? "PATH FINDING..." : (data.message || "ROBOT ALERT");
            } else {
                alertBanner.classList.add('hidden');
            }
        } catch (error) {
            console.error("Alert Poll Error:", error);
        }
    };

    // 4. Command Handlers
    const sendCommand = async (endpoint) => {
        try {
            const response = await fetch(`${API_BASE}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            if (response.ok) {
                console.log(`Command ${endpoint} sent successfully.`);
            } else {
                console.error(`Command ${endpoint} failed.`);
            }
        } catch (error) {
            console.error("Command Error:", error);
        }
    };

    document.getElementById('btn-start').onclick = () => sendCommand('/patrol/start');
    document.getElementById('btn-return').onclick = () => sendCommand('/patrol/return');


    // 6. Intervals
    setInterval(pollStatus, 1000);
    setInterval(pollAlerts, 1000);

    // Initial Trigger
    pollStatus();
    pollAlerts();
});
