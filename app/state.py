import threading
import time

class AppState:
    """Thread-safe application state shared between CV loop and API."""
    def __init__(self):
        self.lock = threading.Lock()
        self.current_frame = None
        self.last_annotated_frame = None
        self.camera_connected = False
        self.last_fall_event = None
        self.current_pan_angle = 90
        self.system_status = "initializing"
        self.start_time = time.time()
        
    def get_status(self):
        with self.lock:
            return {
                "camera_connected": self.camera_connected,
                "last_fall": self.last_fall_event,
                "current_pan_angle": self.current_pan_angle,
                "uptime_seconds": round(time.time() - self.start_time, 2),
                "status": self.system_status
            }
