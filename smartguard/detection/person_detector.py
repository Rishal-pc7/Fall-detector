"""
Multi-person detector using YOLOv8n.

Why YOLOv8n instead of MediaPipe Pose for detection:
  - MediaPipe Pose tracks only ONE person at a time.
  - YOLOv8n (nano, ~6 MB) can detect multiple people reliably on CPU at ~15-20 FPS.
  - We use YOLO purely for bounding-box detection (class 0 = person).
  - Pose landmark extraction is handled separately per-person by MediaPipe if needed.

The ultralytics library also bundles BoT-SORT tracking, which gives us persistent
track IDs across frames without any additional dependency.
"""

import logging
from ultralytics import YOLO

logger = logging.getLogger(__name__)


class PersonDetector:
    """
    Wraps YOLOv8n to detect people in each frame.

    Returns a list of detections, each with (x1, y1, x2, y2, conf, track_id).
    Track IDs are persistent across frames thanks to the built-in BoT-SORT tracker.
    """

    def __init__(self, model_path: str = "yolov8n.pt", confidence: float = 0.5):
        """
        Args:
            model_path: Path to YOLOv8 weights. Will auto-download if not present.
            confidence: Minimum confidence to accept a person detection.
        """
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.person_class_id = 0  # COCO class 0 = person
        logger.info(f"PersonDetector loaded: {model_path} (conf={confidence})")

    def detect_and_track(self, frame):
        """
        Run detection + tracking on a single frame.

        Returns:
            list of dicts, each with keys:
                'track_id' (int), 'bbox' (x1,y1,x2,y2), 'confidence' (float)
            Returns empty list if no people detected.
        """
        # model.track() runs detection + BoT-SORT tracker in one call.
        # persist=True keeps tracker state across calls (essential for stable IDs).
        # verbose=False suppresses per-frame logging.
        results = self.model.track(
            frame,
            persist=True,
            conf=self.confidence,
            classes=[self.person_class_id],
            verbose=False,
        )

        detections = []

        if results and len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes

            for i in range(len(boxes)):
                # Get bounding box in xyxy format (pixel coordinates)
                x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy().astype(int)
                conf = float(boxes.conf[i].cpu().numpy())

                # Track ID (may be None if tracking hasn't assigned one yet)
                track_id = None
                if boxes.id is not None:
                    track_id = int(boxes.id[i].cpu().numpy())

                if track_id is not None:
                    detections.append({
                        "track_id": track_id,
                        "bbox": (int(x1), int(y1), int(x2), int(y2)),
                        "confidence": conf,
                    })

        return detections
