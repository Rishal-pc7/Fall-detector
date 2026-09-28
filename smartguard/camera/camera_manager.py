"""
Threaded camera capture for SmartGuard.

Continuously reads frames from cv2.VideoCapture in a background thread,
writing the latest frame into AppState. The CV pipeline reads from AppState
on its own schedule — this decouples capture FPS from processing FPS.

Camera selection:
  Set CAMERA_INDEX in .env to a specific index (0, 1, 2 …) to use that camera.
  Set CAMERA_INDEX=-1 to auto-detect the first external USB webcam (skips
  built-in cameras and DroidCam).
  Run  python find_usb_camera.py  to list all connected cameras and their indices.
"""

import cv2
import subprocess
import threading
import time
import logging

logger = logging.getLogger(__name__)

# Map string backend names to cv2 constants
_BACKEND_MAP = {
    "dshow":  cv2.CAP_DSHOW,
    "msmf":   cv2.CAP_MSMF,
    "any":    cv2.CAP_ANY,
    "auto":   cv2.CAP_ANY,
}

# Keywords that identify cameras we want to SKIP (not USB webcams)
_SKIP_KEYWORDS = [
    "integrated", "built-in", "internal",
    "ir camera", "windows hello", "infrared",
    "droidcam", "epoccam", "iriun", "camo",   # virtual phone cameras
]

# Keywords that positively identify an external USB webcam
_USB_KEYWORDS = [
    "usb", "external", "logitech", "trust", "canyon", "genius",
    "razer", "microsoft lifecam", "hd webcam", "full hd", "c920",
    "c922", "c270", "brio", "streamcam",
]


def _get_camera_names_windows() -> list[str]:
    """Return list of camera device friendly names from Windows PnP."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-PnpDevice -Class Camera -Status OK | Select-Object -ExpandProperty FriendlyName"],
            capture_output=True, text=True, timeout=5
        )
        return [n.strip() for n in result.stdout.strip().splitlines() if n.strip()]
    except Exception:
        return []


def find_usb_camera_index(max_index: int = 8) -> int:
    """
    Scan available cameras and return the index of the first external USB webcam.

    Strategy:
    1. Get device names from Windows — match by name keywords.
    2. If names not available, fall back to testing each index and picking
       the first one that isn't index 0 (usually built-in).

    Returns the index, or raises RuntimeError if none found.
    """
    names = _get_camera_names_windows()
    logger.info(f"Detected camera devices: {names}")

    # Build a mapping of position → name (Windows lists cameras in index order)
    if names:
        for idx, name in enumerate(names):
            nl = name.lower()
            # Skip known non-USB devices
            if any(k in nl for k in _SKIP_KEYWORDS):
                logger.info(f"  Skipping index {idx}: '{name}' (built-in/virtual)")
                continue
            # Prefer known USB webcam brands/keywords
            if any(k in nl for k in _USB_KEYWORDS):
                logger.info(f"  Selected USB webcam at index {idx}: '{name}'")
                return idx
            # Unknown device — could be USB; accept it if it's not index 0
            if idx > 0:
                logger.info(f"  Selected unknown external camera at index {idx}: '{name}'")
                return idx

    # Fallback: scan OpenCV indices, skip index 0 (almost always built-in)
    logger.warning("Could not identify cameras by name — scanning by index (skipping 0)")
    for i in range(1, max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            cap.release()
            if ret:
                logger.info(f"  Fallback: selected camera at index {i}")
                return i

    raise RuntimeError(
        "No external USB webcam found. "
        "Plug in your USB webcam and set CAMERA_INDEX in .env, "
        "or run  python find_usb_camera.py  to list available cameras."
    )


class CameraManager:
    def __init__(self, camera_index: int, app_state, width: int = 640, height: int = 480, backend: str = "auto"):
        self.app_state = app_state
        self.width = width
        self.height = height
        self.backend = _BACKEND_MAP.get(backend.lower(), cv2.CAP_ANY)
        self.cap = None
        self.running = False
        self.thread = None

        if camera_index == -1:
            logger.info("CAMERA_INDEX=-1: auto-detecting USB webcam...")
            try:
                self.camera_index = find_usb_camera_index()
                logger.info(f"Auto-detected USB webcam at index {self.camera_index}")
            except RuntimeError as e:
                logger.error(str(e))
                self.camera_index = -1  # will fail gracefully in _capture_loop
        else:
            self.camera_index = camera_index

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        logger.info(f"Camera thread started (index={self.camera_index}, backend={self.backend})")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)
        if self.cap:
            self.cap.release()
        logger.info("Camera thread stopped")

    def _capture_loop(self):
        if self.camera_index == -1:
            logger.error("No USB webcam available. Cannot start capture.")
            with self.app_state.lock:
                self.app_state.camera_connected = False
                self.app_state.system_status = "camera_error"
            return

        self.cap = cv2.VideoCapture(self.camera_index, self.backend)

        if not self.cap.isOpened():
            logger.error(f"Cannot open camera index {self.camera_index} with backend {self.backend}")
            with self.app_state.lock:
                self.app_state.camera_connected = False
                self.app_state.system_status = "camera_error"
            return

        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        with self.app_state.lock:
            self.app_state.camera_connected = True
            if self.app_state.system_status == "initializing":
                self.app_state.system_status = "running"

        logger.info(f"Camera opened: {self.width}x{self.height}")

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                logger.warning("Camera read failed, retrying...")
                with self.app_state.lock:
                    self.app_state.camera_connected = False
                time.sleep(0.5)
                continue

            with self.app_state.lock:
                self.app_state.current_frame = frame
                self.app_state.camera_connected = True

            time.sleep(0.005)  # ~200 Hz max poll rate, actual limited by camera
