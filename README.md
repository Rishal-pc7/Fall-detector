# SmartGuard — Multi-Person AI Fall Detection System

A complete, end-to-end multi-person fall detection and recognition system featuring:
- **Computer Vision Pipeline**: YOLOv8n person detection with BoT-SORT persistent tracking.
- **Per-Person State Machine**: Dedicated 6-state temporal fall tracking (`STANDING`, `POSSIBLE_FALL`, `FALLING`, `FALL_CONFIRMED`, `DOWN`, `RECOVERING`).
- **Explainable Biometrics**: Torso angle (90° upright to 0° horizontal), centroid drop velocity, aspect ratio, and 3×3 spatial zone mapping.
- **Face Recognition**: Local OpenCV YuNet detection + SFace embeddings with persistent cosine-distance face matching.
- **Hardware Actuation**: USB Serial protocol (`FALL:<angle>:<x>:<y>\n`) to an Arduino driving a panning servo camera mount.
- **Cloud Synchronization**: Two-step asynchronous Firebase pipeline (Realtime Database initial event with `image_link: null` -> Firebase Storage upload -> Realtime Database update with download URL).
- **Interactive Dashboard**: Modern dark-theme Pygame UI with the rule: *bounding boxes rendered strictly for standing individuals; distinct visual alert targets for falls*.
- **Mobile Companion App**: Flutter application with real-time Firebase listeners and push notifications triggering strictly upon snapshot upload completion.

---

## System Architecture

```
                       [USB / Web Camera]
                               │
                               ▼
                   [Camera Capture Thread]
                               │
                               ▼
    ┌────────────────[AppState (Shared)]────────────────┐
    │                                                   │
    ▼                                                   ▼
[SmartGuard CV Pipeline]                        [Pygame Dashboard]
 ├── YOLOv8n + BoT-SORT                         (Live Feed, Tracks,
 ├── Fall State Machine                         Diagnostics, Alerts)
 ├── YuNet + SFace Face Recog
 └── Event Manager
      │
      ├──> [Arduino Serial] ──────────> [Arduino Servo Mount]
      │    `FALL:<angle>:<x>:<y>\n`
      │
      └──> [Asynchronous Event Queue]
           ├── 1. RTDB: create event (image_link = null)
           ├── 2. Storage: upload fall snapshot (.jpg)
           └── 3. RTDB: update event (image_link = URL)
                               │
                               ▼
                   [SmartGuard Flutter App]
                   (Fires notification when image_link != null)
```

---

## Directory Structure

```text
fall-detection-backend/
├── smartguard/                  # Main SmartGuard backend
│   ├── camera/                  # Threaded camera capture
│   ├── cloud/                   # Firebase RTDB and Storage integration
│   ├── config/                  # Settings and configuration loader
│   ├── detection/               # YOLOv8 detector & per-person FallDetector
│   ├── events/                  # Local event logging & async cloud queue
│   ├── hardware/                # Threaded Arduino serial controller
│   ├── recognition/             # YuNet detector, SFace recognizer, FaceDB
│   ├── state/                   # Thread-safe AppState & PersonState
│   ├── ui/                      # Pygame dashboard
│   ├── pipeline.py              # Main multi-person CV loop
│   ├── utils.py                 # 3x3 zone mapping & angle helpers
│   └── main.py                  # System launcher
├── arduino/
│   └── smartguard_servo.ino     # Arduino serial pan servo sketch
├── smartguard_app/              # Flutter companion mobile app
│   ├── lib/
│   └── pubspec.yaml
├── config.json                  # Tunable parameters (thresholds, angles, UI)
├── .env.example                 # Machine-specific secrets & ports
├── requirements.txt             # Python dependencies
└── tests/                       # Pytest test suite
```

---

## Setup & Quickstart

### 1. Python Environment

Ensure Python 3.10+ is installed:
```bash
# Activate virtual environment
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration (`.env` and `config.json`)

Copy `.env.example` to `.env` and fill in your details:
```bash
cp .env.example .env
```

Key environment variables:
- `CAMERA_INDEX`: `0` for built-in webcam, `1` for external USB camera.
- `ARDUINO_PORT`: Serial port (e.g. `COM3` on Windows, `/dev/ttyUSB0` on Linux).
- `FIREBASE_CREDENTIALS_PATH`: Path to Firebase Service Account JSON key.
- `FIREBASE_DATABASE_URL`: Your Realtime Database URL.
- `FIREBASE_STORAGE_BUCKET`: Your Firebase Storage bucket domain.

All algorithm thresholds (fall confirmation frames, angle limits, servo angles, UI sizes) are live-tunable in `config.json`.

---

## Running SmartGuard

Start the complete SmartGuard system:
```bash
python -m smartguard.main
```
This automatically starts:
1. Arduino Serial communication thread.
2. Firebase asynchronous event queue thread.
3. Threaded camera capture.
4. YOLOv8 multi-person tracking & fall detection pipeline.
5. Pygame dashboard window.

Press `Q` or `ESC` to quit gracefully.

---

## Hardware: Arduino Pan Servo

1. Open `arduino/smartguard_servo.ino` in the Arduino IDE.
2. Connect an SG90 or MG995 servo:
   - **Signal**: Pin 9
   - **VCC**: 5V
   - **GND**: GND
3. Select your board and port, then click **Upload**.
4. Set `ARDUINO_PORT=COM3` in your `.env`.

When a fall is detected, SmartGuard sends:
```text
FALL:<angle>:<x>:<y>\n
```
The Arduino pans toward the subject, holds for 2 seconds, and returns to center.

---

## Mobile Companion App (Flutter)

Located in `smartguard_app/`:
```bash
cd smartguard_app
flutter pub get
flutter run
```
Features:
- Listens to Firebase Realtime Database at `/fall_events`.
- **Notification Rule**: Only dispatches a local emergency notification once the cloud snapshot URL is attached (`image_link != null`), preventing notifications without evidence.
- Full incident history with photo previews and emergency dispatch button.

---

## Running Tests

Execute the automated test suite:
```bash
pytest tests/
```
Tests verify:
- Per-person fall state transitions (standing, possible fall, falling, confirmed, recovery).
- Multi-person state isolation.
- 3×3 spatial zone estimation.
- Arduino serial protocol formatting.
- Local event logging and queueing.
