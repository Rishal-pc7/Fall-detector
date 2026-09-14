import cv2
import mediapipe as mp
import numpy as np

# We use MediaPipe Pose for tracking and fall heuristics to save CPU instead of adding YOLOv8.
# MediaPipe Pose implicitly provides tracking of a single primary person, including a bounding box
# which we calculate by finding the min/max of the detected landmarks.

class PersonDetector:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
    def process(self, frame):
        """
        Returns (landmarks_result, bbox, centroid) or (None, None, None).
        bbox is (x, y, w, h). centroid is (cx, cy).
        """
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(image_rgb)
        
        if not results.pose_landmarks:
            return None, None, None
            
        h, w, _ = frame.shape
        x_coords = [lm.x * w for lm in results.pose_landmarks.landmark]
        y_coords = [lm.y * h for lm in results.pose_landmarks.landmark]
        
        # Calculate bounding box
        x_min = int(max(0, min(x_coords)))
        y_min = int(max(0, min(y_coords)))
        x_max = int(min(w, max(x_coords)))
        y_max = int(min(h, max(y_coords)))
        
        bbox = (x_min, y_min, x_max - x_min, y_max - y_min)
        
        # Calculate centroid (using hip mid-point as centroid makes tracking stable)
        left_hip = results.pose_landmarks.landmark[self.mp_pose.PoseLandmark.LEFT_HIP]
        right_hip = results.pose_landmarks.landmark[self.mp_pose.PoseLandmark.RIGHT_HIP]
        
        cx = int((left_hip.x + right_hip.x) / 2 * w)
        cy = int((left_hip.y + right_hip.y) / 2 * h)
        
        return results, bbox, (cx, cy)
