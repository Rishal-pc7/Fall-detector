"""
SmartGuard Configuration Loader.

Loads settings from config.json (thresholds, UI, servo mappings) and .env (secrets, ports).
config.json holds tunable values that judges may ask about.
.env holds machine-specific secrets (Firebase service-account JSON string, COM port).
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

# ── Load config.json ──────────────────────────────────────────────────────────
_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_smartguard_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_config_candidates = [
    os.path.join(_root_dir, "config.json"),
    os.path.join(_smartguard_dir, "config.json"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
]

CONFIG = {}
for candidate in _config_candidates:
    if os.path.exists(candidate):
        with open(candidate, "r") as f:
            CONFIG = json.load(f)
        break

if not CONFIG:
    raise FileNotFoundError("Could not find config.json in project root or smartguard directory.")

# ── .env overrides / secrets ──────────────────────────────────────────────────
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", str(CONFIG.get("camera", {}).get("index", 0))))
CAMERA_BACKEND = os.getenv("CAMERA_BACKEND", "auto")  # auto | dshow | msmf

ARDUINO_PORT = os.getenv("ARDUINO_PORT", "COM3")
ARDUINO_BAUD = int(os.getenv("ARDUINO_BAUD", "9600"))

# Paste the entire Firebase service-account JSON as a single-line string value.
# No credentials file on disk is required.
FIREBASE_SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "")
FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", "")

YUNET_MODEL_PATH = os.getenv("YUNET_MODEL_PATH", CONFIG.get("recognition", {}).get("yunet_model", "models/face_detection_yunet_2023mar.onnx"))
SFACE_MODEL_PATH = os.getenv("SFACE_MODEL_PATH", CONFIG.get("recognition", {}).get("sface_model", "models/face_recognition_sface_2021dec.onnx"))
SFACE_MATCH_THRESHOLD = float(os.getenv("SFACE_MATCH_THRESHOLD", str(CONFIG.get("recognition", {}).get("confidence_threshold", 0.363))))

FALL_COOLDOWN_SECONDS = int(os.getenv("FALL_COOLDOWN_SECONDS", str(CONFIG.get("fall", {}).get("cooldown_seconds", 30))))

