"""
Pose Estimator wrapping Ultralytics YOLO-pose model.
Used for per-person posture extraction on cropped images.
"""

import logging
import numpy as np
from typing import Dict, Any, Optional
from ultralytics import YOLO

logger = logging.getLogger(__name__)


class PoseEstimator:
    def __init__(self, model_path: str = "yolov8n-pose.pt", confidence: float = 0.4):
        self.model = YOLO(model_path)
        self.confidence = confidence
        logger.info(f"PoseEstimator loaded: {model_path} (conf={confidence})")

        # Ultralytics Keypoint Indices (COCO format)
        self.KEYPOINT_MAP = {
            "nose": 0,
            "left_shoulder": 5,
            "right_shoulder": 6,
            "left_hip": 11,
            "right_hip": 12,
            "left_knee": 13,
            "right_knee": 14,
            "left_ankle": 15,
            "right_ankle": 16,
        }

    def estimate(self, crop: np.ndarray) -> Optional[Dict[str, tuple]]:
        """
        Run pose estimation on a cropped person image.
        Returns a dictionary of keypoints relative to the crop origin,
        or None if no person/pose is detected in the crop.
        Each value is a tuple (x, y, confidence).
        """
        if crop.size == 0 or crop.shape[0] < 10 or crop.shape[1] < 10:
            return None

        # Run inference (verbose=False to avoid console spam)
        results = self.model(crop, verbose=False, conf=self.confidence)

        if not results or len(results) == 0:
            return None

        result = results[0]
        if result.keypoints is None or result.keypoints.data is None or len(result.keypoints.data) == 0:
            return None

        # Take the first detected pose in the crop
        keypoints = result.keypoints.data[0].cpu().numpy()  # shape (17, 3)

        pose_data = {}
        for name, idx in self.KEYPOINT_MAP.items():
            if idx < len(keypoints):
                x, y, conf = keypoints[idx]
                if conf >= self.confidence:
                    pose_data[name] = (float(x), float(y), float(conf))
                else:
                    pose_data[name] = None
            else:
                pose_data[name] = None

        return pose_data
