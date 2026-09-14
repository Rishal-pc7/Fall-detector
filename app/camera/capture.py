import cv2
import threading
import time

class VideoCaptureThread:
    def __init__(self, camera_index, app_state):
        self.camera_index = camera_index
        self.app_state = app_state
        self.cap = None
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        if self.cap:
            self.cap.release()

    def _update(self):
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            with self.app_state.lock:
                self.app_state.system_status = "camera_error"
                self.app_state.camera_connected = False
            return
            
        with self.app_state.lock:
            self.app_state.camera_connected = True
            if self.app_state.system_status == "initializing":
                self.app_state.system_status = "running"
                
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1)
                continue
                
            # Keep original resolution but could resize here if needed
            with self.app_state.lock:
                self.app_state.current_frame = frame.copy()
            
            # small sleep to avoid maxing out a core just polling
            time.sleep(0.01)
