let html5QrcodeScanner = null;
let isProcessing = false;
let autoResumeTimer = null;
let currentFacingMode = "environment"; // default to back camera

document.addEventListener('DOMContentLoaded', () => {
    initScanner();

    document.getElementById('scanNextBtn').addEventListener('click', resumeScanning);
    document.getElementById('switchCameraBtn').addEventListener('click', switchCamera);

    document.getElementById('manualTokenForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const input = document.getElementById('manualTokenInput');
        const token = input.value.strip ? input.value.strip() : input.value.trim();
        if (token) {
            processQrToken(token);
            input.value = '';
        }
    });
});

async function initScanner() {
    try {
        html5QrcodeScanner = new Html5Qrcode("reader");

        const config = {
            fps: 15,
            qrbox: { width: 220, height: 220 },
            aspectRatio: 1.0
        };

        await html5QrcodeScanner.start(
            { facingMode: currentFacingMode },
            config,
            onScanSuccess,
            onScanFailure
        );
    } catch (err) {
        console.error("Camera access error:", err);
        // Fallback to any camera if environment camera fails
        try {
            await html5QrcodeScanner.start(
                { facingMode: "user" },
                { fps: 15, qrbox: { width: 220, height: 220 } },
                onScanSuccess,
                onScanFailure
            );
        } catch (fallbackErr) {
            console.error("Camera fallback failed:", fallbackErr);
        }
    }
}

async function switchCamera() {
    if (html5QrcodeScanner && html5QrcodeScanner.isScanning) {
        await html5QrcodeScanner.stop();
        currentFacingMode = (currentFacingMode === "environment") ? "user" : "environment";
        await initScanner();
    }
}

function onScanSuccess(decodedText, decodedResult) {
    if (isProcessing) return; // Prevent duplicate triggers while processing
    processQrToken(decodedText);
}

function onScanFailure(error) {
    // Ignore minor scanning frame glitches
}

async function processQrToken(token) {
    if (isProcessing) return;
    isProcessing = true;

    // Show scanner processing overlay
    document.getElementById('scannerOverlay').classList.remove('d-none');

    // Pause html5Qrcode scanner if running
    if (html5QrcodeScanner && html5QrcodeScanner.isScanning) {
        try {
            html5QrcodeScanner.pause(true);
        } catch (e) {
            console.warn("Pause failed", e);
        }
    }

    try {
        const response = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: token.trim() })
        });

        const data = await response.json();
        renderResult(data);
    } catch (err) {
        console.error("Scan API Error:", err);
        renderResult({
            status: "CONNECTION_ERROR",
            message: "CONNECTION ERROR — RETRY",
            student: null
        });
    } finally {
        document.getElementById('scannerOverlay').classList.add('d-none');
    }
}

function renderResult(data) {
    const card = document.getElementById('resultCard');
    const statusIcon = document.getElementById('resultStatusIcon');
    const statusText = document.getElementById('resultStatusText');
    const detailsBox = document.getElementById('studentDetailsBox');
    const nameEl = document.getElementById('studentName');
    const rollEl = document.getElementById('studentRoll');
    const timeCol = document.getElementById('usageTimeCol');
    const timeEl = document.getElementById('usageTime');

    // Reset card classes
    card.className = "card result-card border-0 shadow-lg rounded-4 my-3";
    detailsBox.classList.remove('d-none');
    timeCol.classList.remove('d-none');

    switch (data.status) {
        case 'ALLOWED':
            card.classList.add('status-allowed');
            statusIcon.innerHTML = '<i class="bi bi-check-circle-fill text-white"></i>';
            statusText.textContent = "✅ REGISTERED — ENTRY ALLOWED";
            nameEl.textContent = data.student.name;
            rollEl.textContent = data.student.roll_number;
            timeEl.textContent = data.student.checked_in_at || data.student.used_at || "Just now";
            playBeep('success');
            break;

        case 'ALREADY_CHECKED_IN':
        case 'ALREADY_USED':
            card.classList.add('status-already-used');
            statusIcon.innerHTML = '<i class="bi bi-exclamation-circle-fill text-white"></i>';
            statusText.textContent = "⚠️ ALREADY CHECKED IN";
            nameEl.textContent = data.student.name;
            rollEl.textContent = data.student.roll_number;
            timeEl.textContent = data.student.checked_in_at || data.student.used_at || "Previously checked in";
            playBeep('error');
            break;

        case 'NOT_REGISTERED':
        case 'NOT_ELIGIBLE':
            card.classList.add('status-not-eligible');
            statusIcon.innerHTML = '<i class="bi bi-x-circle-fill text-white"></i>';
            statusText.textContent = "❌ NOT REGISTERED";
            if (data.student) {
                nameEl.textContent = data.student.name;
                rollEl.textContent = data.student.roll_number;
                timeCol.classList.add('d-none');
            } else if (data.roll_number) {
                nameEl.textContent = "Unregistered Student";
                rollEl.textContent = data.roll_number;
                timeCol.classList.add('d-none');
            } else {
                detailsBox.classList.add('d-none');
            }
            playBeep('error');
            break;

        case 'INVALID_QR':
            card.classList.add('status-invalid-qr');
            statusIcon.innerHTML = '<i class="bi bi-qr-code text-white"></i>';
            statusText.textContent = "❌ INVALID QR";
            detailsBox.classList.add('d-none');
            playBeep('error');
            break;

        case 'CONNECTION_ERROR':
        default:
            card.classList.add('status-connection-error');
            statusIcon.innerHTML = '<i class="bi bi-wifi-off text-white"></i>';
            statusText.textContent = "⚠️ CONNECTION ERROR — RETRY";
            detailsBox.classList.add('d-none');
            playBeep('error');
            break;
    }

    card.classList.remove('d-none');

    // Auto-resume after 3.0 seconds
    clearTimeout(autoResumeTimer);
    autoResumeTimer = setTimeout(resumeScanning, 3000);
}

function resumeScanning() {
    clearTimeout(autoResumeTimer);
    document.getElementById('resultCard').classList.add('d-none');
    isProcessing = false;

    if (html5QrcodeScanner) {
        try {
            html5QrcodeScanner.resume();
        } catch (e) {
            console.warn("Resume failed", e);
        }
    }
}

// Audio Feedback System (Web Audio API)
function playBeep(type) {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.connect(gain);
        gain.connect(ctx.destination);

        if (type === 'success') {
            osc.type = 'sine';
            osc.frequency.setValueAtTime(880, ctx.currentTime); // High A5 pitch
            gain.gain.setValueAtTime(0.3, ctx.currentTime);
            osc.start();
            osc.stop(ctx.currentTime + 0.2);
        } else {
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(220, ctx.currentTime); // Low A3 pitch
            gain.gain.setValueAtTime(0.4, ctx.currentTime);
            osc.start();
            osc.stop(ctx.currentTime + 0.35);
        }
    } catch (e) {
        // Audio playback muted or unsupported
    }
}
