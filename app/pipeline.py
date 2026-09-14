import cv2
import time
import threading
import asyncio
from app import config
from app.actuation import servo_client

class MainLoop:
    def __init__(self, app_state, person_detector, fall_detector, face_detector, face_recognizer, face_db, alert_manager):
        self.app_state = app_state
        self.person_detector = person_detector
        self.fall_detector = fall_detector
        self.face_detector = face_detector
        self.face_recognizer = face_recognizer
        self.face_db = face_db
        self.alert_manager = alert_manager
        
        self.running = False
        self.thread = None
        self.last_pan_time = 0.0
        
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
            
    def _run_loop(self):
        # We need an event loop for async httpx calls inside the thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            with self.app_state.lock:
                frame = self.app_state.current_frame
                
            if frame is None:
                time.sleep(0.05)
                continue
                
            # Create a copy for drawing
            annotated_frame = frame.copy()
            
            # 1. Person Detection & Pose
            results, bbox, centroid = self.person_detector.process(frame)
            
            if bbox:
                x, y, w, h = bbox
                cv2.rectangle(annotated_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cx, cy = centroid
                cv2.circle(annotated_frame, (cx, cy), 5, (0, 0, 255), -1)
                
                # 2. Pan Servo Tracking
                current_time = time.time()
                if current_time - self.last_pan_time > config.PAN_UPDATE_INTERVAL_SECONDS:
                    # Calculate angle: simple proportional mapping
                    # Center of frame is 90 degrees
                    frame_w = frame.shape[1]
                    # Error from center
                    error = cx - (frame_w / 2)
                    # Mapping: e.g. 1 pixel = 0.1 degrees
                    with self.app_state.lock:
                        last_angle = self.app_state.current_pan_angle
                    
                    target_angle = int(90 - (error * 0.1)) # Negative because standard servos are mirrored 
                    
                    # Send angle (fire and forget using loop.run_until_complete)
                    if abs(target_angle - last_angle) >= 3:
                        sent_angle = loop.run_until_complete(servo_client.send_pan_angle(target_angle, last_angle))
                        with self.app_state.lock:
                            self.app_state.current_pan_angle = sent_angle
                            
                    self.last_pan_time = current_time
                    
                # 3. Fall Detection
                is_fall = self.fall_detector.check_fall(results, bbox)
                if is_fall:
                    # 4. Face Recognition (Best effort)
                    faces = self.face_detector.detect(frame)
                    person_name = "Unknown"
                    confidence = 0.0
                    
                    if len(faces) > 0:
                        face = faces[0]
                        aligned_face = self.face_recognizer.align_crop(frame, face)
                        feature = self.face_recognizer.feature(aligned_face)
                        matched_name, score = self.face_db.match(self.face_recognizer, feature, config.SFACE_MATCH_THRESHOLD)
                        if matched_name:
                            person_name = matched_name
                            confidence = score
                            
                    # Draw fall alert on frame
                    cv2.putText(annotated_frame, f"FALL: {person_name}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    
                    # 5. Alert Manager
                    loop.run_until_complete(self.alert_manager.process_fall(self.app_state, annotated_frame, person_name, confidence))
                    
            with self.app_state.lock:
                self.app_state.last_annotated_frame = annotated_frame
                
            time.sleep(0.01)
