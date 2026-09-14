"""
SmartGuard Computer Vision Pipeline.

Ties together:
1. Multi-person detection and tracking (YOLOv8n + BoT-SORT)
2. Per-person fall detection state machine (FallDetector)
3. Face detection and recognition (OpenCV YuNet + SFace + FaceDB)
4. Position zone estimation and torso angle calculation
5. Event dispatching (Local logging, Arduino pan command, Firebase cloud queue)
6. Real-time updates to shared AppState
"""

import os
import cv2
import time
import logging
import threading
import numpy as np

from smartguard.state.app_state import AppState
from smartguard.state.person_state import PersonState, FallState
from smartguard.detection.person_detector import PersonDetector
from smartguard.detection.fall_detector import FallDetector
from smartguard.detection.pose_estimator import PoseEstimator
from smartguard.events.event_manager import EventManager
from smartguard.utils import compute_position

logger = logging.getLogger(__name__)


class SmartGuardPipeline:
    def __init__(self, app_state: AppState, config: dict, event_manager: EventManager):
        self.app_state = app_state
        self.config = config
        self.event_manager = event_manager

        # 1. Person Detection & Tracking
        det_cfg = config.get("detection", {})
        model_name = det_cfg.get("model", "yolov8n.pt")
        conf = det_cfg.get("confidence", 0.5)
        self.person_detector = PersonDetector(model_path=model_name, confidence=conf)

        # 2. Per-Person Fall Detection State Machine
        fall_cfg = config.get("fall", {})
        self.fall_detector = FallDetector(fall_cfg)
        self.cooldown_seconds = fall_cfg.get("cooldown_seconds", 30)

        # 3. Pose Estimation
        pose_cfg = config.get("pose", {})
        self.pose_enabled = pose_cfg.get("enabled", True)
        self.pose_every_n = pose_cfg.get("run_every_n_frames", 1)
        self.pose_estimator = None
        if self.pose_enabled:
            model_path = pose_cfg.get("model", "yolov8n-pose.pt")
            conf = pose_cfg.get("confidence_threshold", 0.4)
            try:
                self.pose_estimator = PoseEstimator(model_path=model_path, confidence=conf)
            except Exception as e:
                logger.error(f"Failed to load PoseEstimator: {e}")
                self.pose_estimator = None

        self.running = False
        self.thread = None
        self.frame_count = 0
        self.fps_timer = time.time()
        self.fps_frames = 0

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("SmartGuard CV Pipeline started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)
        logger.info("SmartGuard CV Pipeline stopped")

    def _run_loop(self):
        while self.running:
            # 1. Fetch current camera frame
            frame = None
            with self.app_state.lock:
                if self.app_state.current_frame is not None:
                    frame = self.app_state.current_frame.copy()

            if frame is None:
                time.sleep(0.02)
                continue

            self.frame_count += 1
            self.fps_frames += 1
            frame_h, frame_w, _ = frame.shape

            # Compute and update FPS
            now = time.time()
            if now - self.fps_timer >= 1.0:
                with self.app_state.lock:
                    self.app_state.fps = round(self.fps_frames / (now - self.fps_timer), 1)
                self.fps_frames = 0
                self.fps_timer = now

            # 2. Run Person Detection + Tracking (YOLOv8 + BoT-SORT)
            detections = self.person_detector.detect_and_track(frame)
            real_active_ids = {det["track_id"] for det in detections}
            active_ids = set(real_active_ids)

            # --- Post-Fall Track Persistence ---
            all_ids = set(self.app_state.get_all_people().keys())
            stale_ids = all_ids - real_active_ids
            post_fall_hold = self.config.get("tracking", {}).get("post_fall_track_hold_seconds", 2.5)

            for tid in stale_ids:
                person = self.app_state.people[tid]
                
                # Transition into POST_FALL_PENDING if dropped while falling
                if person.fall_state in (FallState.POSSIBLE_FALL, FallState.FALLING):
                    person.fall_state = FallState.POST_FALL_PENDING
                    person.post_fall_timer_start = now
                    person.reason_for_track_loss = "temporary_detector_loss"
                    logger.warning(f"Track #{tid}: transitioned to POST_FALL_PENDING. Detector lost person.")

                # Retain track if it's pending and within timeout
                if person.fall_state == FallState.POST_FALL_PENDING:
                    if now - person.post_fall_timer_start <= post_fall_hold:
                        active_ids.add(tid)
                        if person.last_known_snapshot:
                            person.bbox = person.last_known_snapshot.get("last_bbox", person.bbox)
                            person.center_x, person.center_y = person.last_known_snapshot.get("last_center", (person.center_x, person.center_y))
                            person.ground_x, person.ground_y = person.last_known_snapshot.get("last_ground_point", (person.ground_x, person.ground_y))
                    else:
                        logger.info(f"Track #{tid}: POST_FALL_PENDING expired. Removing track.")

            # Update state for real detections
            for det in detections:
                track_id = det["track_id"]
                bbox = det["bbox"]

                x1, y1, x2, y2 = bbox
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(frame_w, x2), min(frame_h, y2)

                person = self.app_state.get_or_create_person(track_id)
                
                if person.fall_state == FallState.POST_FALL_PENDING:
                    logger.info(f"Track #{track_id} reacquired from POST_FALL_PENDING -> FALLING")
                    person.fall_state = FallState.FALLING
                    
                person.bbox = (x1, y1, x2, y2)

                # 3. Position & Zone Calculation
                pos_info = compute_position(person.bbox, frame_w, frame_h)
                person.center_x = pos_info["center_x"]
                person.center_y = pos_info["center_y"]
                person.ground_x = pos_info["ground_x"]
                person.ground_y = pos_info["ground_y"]
                person.normalized_x = pos_info["normalized_x"]
                person.normalized_y = pos_info["normalized_y"]
                person.position_zone = pos_info["position_zone"]

            # Process all active tracks (real + pending)
            for track_id in active_ids:
                person = self.app_state.people[track_id]
                is_real = track_id in real_active_ids

                # 4. Pose Estimation (per tracked person)
                if is_real and self.pose_estimator and (self.frame_count % self.pose_every_n == 0):
                    px1, py1, px2, py2 = person.bbox
                    crop = frame[py1:py2, px1:px2]
                    
                    pose_data = self.pose_estimator.estimate(crop)
                    
                    if pose_data is not None:
                        person.pose_available = True
                        
                        # Map crop coordinates back to full frame
                        def map_pt(pt_data):
                            if pt_data is None:
                                return None
                            return (pt_data[0] + px1, pt_data[1] + py1, pt_data[2])
                            
                        person.nose = map_pt(pose_data.get("nose"))
                        person.left_shoulder = map_pt(pose_data.get("left_shoulder"))
                        person.right_shoulder = map_pt(pose_data.get("right_shoulder"))
                        person.left_hip = map_pt(pose_data.get("left_hip"))
                        person.right_hip = map_pt(pose_data.get("right_hip"))
                        person.left_knee = map_pt(pose_data.get("left_knee"))
                        person.right_knee = map_pt(pose_data.get("right_knee"))
                        person.left_ankle = map_pt(pose_data.get("left_ankle"))
                        person.right_ankle = map_pt(pose_data.get("right_ankle"))
                        
                        # Derive centers
                        if person.left_shoulder and person.right_shoulder:
                            person.shoulder_center = (
                                (person.left_shoulder[0] + person.right_shoulder[0]) / 2,
                                (person.left_shoulder[1] + person.right_shoulder[1]) / 2
                            )
                        else:
                            person.shoulder_center = None
                            
                        if person.left_hip and person.right_hip:
                            person.hip_center = (
                                (person.left_hip[0] + person.right_hip[0]) / 2,
                                (person.left_hip[1] + person.right_hip[1]) / 2
                            )
                        else:
                            person.hip_center = None
                    else:
                        person.pose_available = False

                # 5. Fall Detection State Machine
                fire_event = self.fall_detector.update(person, frame_h, frame_w)

                # Save snapshot if actively falling
                if is_real and person.fall_state in (FallState.POSSIBLE_FALL, FallState.FALLING, FallState.FALL_CONFIRMED):
                    person.last_known_snapshot = {
                        "last_bbox": person.bbox,
                        "last_center": (person.center_x, person.center_y),
                        "last_ground_point": (person.ground_x, person.ground_y),
                        "last_body_angle": person.body_angle,
                        "last_fall_confidence": person.fall_confidence,
                        "last_seen_timestamp": now
                    }

                if fire_event and not person.event_created:
                    if now - person.last_event_time >= self.cooldown_seconds:
                        logger.warning(f"🚨 CONFIRMED FALL for person #{person.track_id}! Dispatching event.")
                        person.last_event_time = now
                        person.event_created = True

                        event_data = self.event_manager.handle_fall_confirmed(person, frame)
                        with self.app_state.lock:
                            self.app_state.last_fall_event = event_data

            # 6. Cleanup Stale Tracks
            self.app_state.remove_stale_tracks(active_ids)

            # Prevent 100% CPU spinning
            time.sleep(0.005)
