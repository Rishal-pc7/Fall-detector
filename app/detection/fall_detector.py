import collections
import math
import mediapipe as mp

class FallDetector:
    def __init__(self, 
                 aspect_ratio_threshold=1.0, 
                 fast_drop_threshold=0.08, # Normalized y distance per frame (~8% of height)
                 torso_angle_threshold=60, # Degrees from vertical
                 sustained_frames_threshold=10, # Frames to sustain lying posture
                 history_size=30):
        self.aspect_ratio_threshold = aspect_ratio_threshold
        self.fast_drop_threshold = fast_drop_threshold
        self.torso_angle_threshold = torso_angle_threshold
        self.sustained_frames_threshold = sustained_frames_threshold
        
        # Rolling window histories
        self.centroid_y_history = collections.deque(maxlen=history_size)
        self.torso_angle_history = collections.deque(maxlen=history_size)
        
        self.mp_pose = mp.solutions.pose
        self.fall_sustained_count = 0
        
    def check_fall(self, results, bbox):
        """
        Stateful heuristic over N frames:
        1. Torso angle relative to vertical crosses threshold (near 90 is lying down).
        2. Centroid Y velocity exceeded fast drop threshold in recent frames.
        3. Sustained horizontal position.
        """
        if not results or not bbox:
            return False
            
        _, _, w, h = bbox
        
        # 1. Aspect Ratio
        # Spikes toward/above 1.0 when a person goes from standing to lying down.
        aspect_ratio = w / h if h > 0 else 0
        
        landmarks = results.pose_landmarks.landmark
        
        # Calculate torso angle relative to vertical
        # Midpoint of shoulders
        left_shoulder = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]
        shoulder_mid_x = (left_shoulder.x + right_shoulder.x) / 2
        shoulder_mid_y = (left_shoulder.y + right_shoulder.y) / 2
        
        # Midpoint of hips
        left_hip = landmarks[self.mp_pose.PoseLandmark.LEFT_HIP]
        right_hip = landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP]
        hip_mid_x = (left_hip.x + right_hip.x) / 2
        hip_mid_y = (left_hip.y + right_hip.y) / 2
        
        self.centroid_y_history.append(hip_mid_y)
        
        dx = hip_mid_x - shoulder_mid_x
        dy = hip_mid_y - shoulder_mid_y
        
        # Angle from vertical (0 is perfectly upright, 90 is lying flat)
        # Using atan2 to get the angle, then convert to degrees, mapping vertical to 0.
        angle = math.degrees(math.atan2(abs(dx), abs(dy))) 
        self.torso_angle_history.append(angle)
        
        # Check conditions
        is_horizontal = angle > self.torso_angle_threshold or aspect_ratio > self.aspect_ratio_threshold
        
        # Check if there was a fast drop recently
        fast_drop = False
        if len(self.centroid_y_history) >= 5:
            # Look at velocity over the last few frames
            recent_y = list(self.centroid_y_history)[-5:]
            drop_velocity = recent_y[-1] - recent_y[0]
            if drop_velocity > self.fast_drop_threshold:
                fast_drop = True
                
        if is_horizontal:
            # Only count as a fall if we've seen a fast drop recently, 
            # or if we are already sustaining a fall count.
            if fast_drop or self.fall_sustained_count > 0:
                self.fall_sustained_count += 1
        else:
            self.fall_sustained_count = 0
            
        if self.fall_sustained_count >= self.sustained_frames_threshold:
            # Reset after triggering to avoid continuous immediate triggers 
            # (alert manager cooldown handles the rest)
            self.fall_sustained_count = 0 
            return True
            
        return False
