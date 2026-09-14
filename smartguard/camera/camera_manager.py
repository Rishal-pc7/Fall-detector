"""
Threaded camera capture for SmartGuard.

Continuously reads frames from cv2.VideoCapture in a background thread,
writing the latest frame into AppState. The CV pipeline reads from AppState
on its own schedule — this decouples capture FPS from processing FPS.
"""

import cv2
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


class CameraManager:
    def __init__(self, camera_index: int, app_state, width: int = 640, height: int = 480, backend: str = "auto"):
        self.camera_index = camera_index
        self.app_state = app_state
        self.width = width
        self.height = height
        self.backend = _BACKEND_MAP.get(backend.lower(), cv2.CAP_ANY)
        self.cap = None
        self.running = False
        self.thread = None

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
