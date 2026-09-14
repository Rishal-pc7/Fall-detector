import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ESP32_BASE_URL = os.getenv("ESP32_BASE_URL", "http://192.168.1.50")
FALL_COOLDOWN_SECONDS = int(os.getenv("FALL_COOLDOWN_SECONDS", "60"))
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
PAN_UPDATE_INTERVAL_SECONDS = float(os.getenv("PAN_UPDATE_INTERVAL_SECONDS", "0.5"))
YUNET_MODEL_PATH = os.getenv("YUNET_MODEL_PATH", "models/face_detection_yunet_2023mar.onnx")
SFACE_MODEL_PATH = os.getenv("SFACE_MODEL_PATH", "models/face_recognition_sface_2021dec.onnx")
SFACE_MATCH_THRESHOLD = float(os.getenv("SFACE_MATCH_THRESHOLD", "0.363"))
