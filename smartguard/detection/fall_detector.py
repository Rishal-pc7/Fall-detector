"""
Per-person temporal fall detection state machine for SmartGuard.

Each tracked person gets their own independent fall detection state.
The detector processes ONE person's data at a time — it is called once
per person per frame from the main pipeline.

State Machine:
    STANDING → SITTING           (controlled descent, stable posture)
    STANDING → POSSIBLE_FALL     (rapid downward motion + orientation change)
    SITTING  → POSSIBLE_FALL     (rapid drop from seated position)
    POSSIBLE_FALL → FALLING      (sustained abnormal posture)
    FALLING → FALL_CONFIRMED     (persistent abnormal posture)
    FALLING → POST_FALL_PENDING  (detector temporarily lost track after fall)
    POST_FALL_PENDING → FALL_CONFIRMED

Fall detection is TEMPORAL — it evaluates motion history (velocity,
displacement, angle change rate), NOT single-frame posture snapshots.
A low torso angle alone does NOT trigger a fall. SITTING requires
observed active controlled descent from a verified standing state.
"""

import math
import logging
from smartguard.state.person_state import PersonState, FallState, Posture

logger = logging.getLogger(__name__)


class FallDetector:
    """
    Stateful per-person temporal fall detector.

    Call `update(person, frame_height, frame_width)` once per person per frame.
    The method mutates the PersonState in-place (fall_state, body_angle, etc.).
    """

    def __init__(self, config: dict):
        self.confirmation_frames = config.get("confirmation_frames", 15)
        self.possible_fall_frames = config.get("possible_fall_frames", 5)
        
        # New temporal motion thresholds
        self.min_downward_velocity = config.get("min_downward_velocity", 0.04)
        self.min_vertical_displacement = config.get("min_vertical_displacement", 0.10)
        self.torso_angle_threshold = config.get("torso_angle_threshold", 50)
        self.aspect_ratio_threshold = config.get("aspect_ratio_threshold", 1.1)

    def compute_body_angle(self, person: PersonState, frame_h: int, frame_w: int) -> float:
        """
        Compute body angle from pose landmarks if available,
        otherwise estimate from bounding box aspect ratio.
        """
        if person.pose_available and person.shoulder_center and person.hip_center:
            dx = person.hip_center[0] - person.shoulder_center[0]
            dy = person.hip_center[1] - person.shoulder_center[1]
            angle_from_vertical = math.degrees(math.atan2(abs(dx), abs(dy)))
            angle = max(0.0, min(90.0, 90.0 - angle_from_vertical))
            person.pose_torso_angle = angle
            person.pose_torso_angle_history.append(angle)
            return angle

        # Fallback to bounding box geometry
        if person.bbox:
            x1, y1, x2, y2 = person.bbox
            w = max(1, x2 - x1)
            h = max(1, y2 - y1)
            ratio = w / h
            return max(0.0, min(90.0, 90.0 - (ratio - 0.5) * 60.0))

        return 90.0

    def update(self, person: PersonState, frame_h: int, frame_w: int) -> bool:
        """
        Update fall state for a single person. Called once per frame.
        """
        if person.bbox is None:
            return False

        x1, y1, x2, y2 = person.bbox
        w = max(1, x2 - x1)
        h = max(1, y2 - y1)

        # ── Compute signals ──────────────────────────────────────────────
        body_angle = self.compute_body_angle(person, frame_h, frame_w)
        person.body_angle = round(body_angle, 1)
        person.angle_history.append(body_angle)

        centroid_y = ((y1 + y2) / 2) / frame_h
        person.centroid_y_history.append(centroid_y)

        aspect_ratio = w / h

        # ── Update Static Posture ────────────────────────────────────────
        if body_angle < 30 or aspect_ratio > self.aspect_ratio_threshold:
            person.posture = Posture.HORIZONTAL
        elif body_angle < self.torso_angle_threshold or aspect_ratio > 0.8:
            person.posture = Posture.SEATED
        else:
            person.posture = Posture.UPRIGHT

        # ── Head Tracking for Velocity (Hybrid) ──────────────────────────
        bbox_head_y = y1 / frame_h
        person.head_y_history.append(bbox_head_y)
        
        pose_head_y = None
        if person.pose_available:
            if person.nose:
                pose_head_y = person.nose[1] / frame_h
            elif person.shoulder_center:
                pose_head_y = person.shoulder_center[1] / frame_h
                
        if pose_head_y is not None:
            person.nose_y_history.append(pose_head_y)
        elif len(person.nose_y_history) > 0:
            person.nose_y_history.append(person.nose_y_history[-1])

        # ── Motion dynamics (Temporal) ───────────────────────────────────
        def calc_motion(hist_list):
            c_vel = 0.0
            m_vel = 0.0
            disp = 0.0
            if len(hist_list) >= 5:
                recent_avg = (hist_list[-1] + hist_list[-2]) / 2
                past_avg = (hist_list[-4] + hist_list[-5]) / 2
                c_vel = recent_avg - past_avg
                
                lookback = min(len(hist_list), 15)
                window = hist_list[-lookback:]
                for i in range(4, len(window)):
                    r_avg = (window[i] + window[i-1]) / 2
                    p_avg = (window[i-3] + window[i-4]) / 2
                    v = r_avg - p_avg
                    if v > m_vel:
                        m_vel = v
            if len(hist_list) >= 15:
                disp = hist_list[-1] - hist_list[-15]
            return c_vel, m_vel, disp

        bbox_cvel, bbox_mvel, bbox_disp = calc_motion(list(person.head_y_history))
        pose_cvel, pose_mvel, pose_disp = 0.0, 0.0, 0.0
        
        if len(person.nose_y_history) >= 5:
            pose_cvel, pose_mvel, pose_disp = calc_motion(list(person.nose_y_history))

        # Hybrid fusion: prioritizing pose evidence if significant, otherwise max
        current_velocity = max(bbox_cvel, pose_cvel)
        max_velocity = max(bbox_mvel, pose_mvel)
        displacement = max(bbox_disp, pose_disp)

        # Angle change rate over last 5 frames
        angle_change = 0.0
        if len(person.angle_history) >= 5:
            angle_change = abs(list(person.angle_history)[-1] - list(person.angle_history)[-5])

        # ── Fall Score ───────────────────────────────────────────────────
        # Weighted combination of temporal motion evidence.
        fall_score = 0.0
        
        # 1. Velocity (Immediate motion)
        if max_velocity > self.min_downward_velocity:
            fall_score += 0.3
            if max_velocity > 0.07:  # Very fast drop
                fall_score += 0.2
                
        # 2. Displacement (Sustained motion)
        if displacement > self.min_vertical_displacement:
            fall_score += 0.3
        
        # 3. Posture (Significant orientation change)
        # SITTING posture alone is not fall evidence. Only HORIZONTAL posture 
        # strongly contributes to a fall score.
        if person.posture == Posture.HORIZONTAL:
            fall_score += 0.3

        # ── State machine transitions (Event-based) ──────────────────────
        fire_event = False
        state = person.fall_state
        prev_state = state

        # Helper for detailed logging
        def log_transition(new_state, trigger_reason=""):
            logger.warning(
                f"\n--- STATE TRANSITION ---"
                f"\nTrack {person.track_id}: {prev_state.value} -> {new_state.value}"
                f"\nTrigger: {trigger_reason}"
                f"\nbody_angle={person.body_angle}°"
                f"\npose_angle={person.pose_torso_angle}°"
                f"\nangle_change={angle_change:.1f}°"
                f"\ncenter_x={person.center_x:.3f}"
                f"\ncenter_y={person.center_y:.3f}"
                f"\nvertical_displacement={displacement:.3f} (bbox={bbox_disp:.3f}, pose={pose_disp:.3f})"
                f"\nvertical_velocity={current_velocity:.3f} (max={max_velocity:.3f}, bbox_max={bbox_mvel:.3f}, pose_max={pose_mvel:.3f})"
                f"\nbbox_width={w}"
                f"\nbbox_height={h}"
                f"\naspect_ratio={aspect_ratio:.2f}"
                f"\nfall_score={fall_score:.2f}"
                f"\nfall_confidence={person.fall_confidence:.2f}"
                f"\nposture={person.posture.value}"
                f"\npose_available={person.pose_available}"
                f"\n------------------------"
            )

        if state == FallState.NORMAL:
            person.state_frame_count += 1
            # Rapid descent + posture change = possible fall
            # Rapid descent + posture change = possible fall
            # Explicitly require downward velocity to trigger a fall, suppressing static false positives
            if fall_score >= 0.75 and max_velocity > self.min_downward_velocity:
                person.fall_state = FallState.POSSIBLE_FALL
                person.state_frame_count = 1
                person.fall_confidence = min(1.0, fall_score)
                log_transition(FallState.POSSIBLE_FALL, f"fall_score={fall_score:.2f} >= 0.75 & max_vel={max_velocity:.3f}")

        elif state == FallState.POSSIBLE_FALL:
            if person.posture != Posture.UPRIGHT:
                person.state_frame_count += 1
                person.fall_confidence = min(0.6, 0.3 + person.state_frame_count * 0.05)
                if person.state_frame_count >= self.possible_fall_frames:
                    person.fall_state = FallState.FALLING
                    person.state_frame_count = 0
                    log_transition(FallState.FALLING, f"posture != UPRIGHT for {self.possible_fall_frames} frames")
            else:
                person.reset_fall_state()
                log_transition(FallState.NORMAL, "posture became UPRIGHT")

        elif state == FallState.FALLING:
            if person.posture != Posture.UPRIGHT:
                person.state_frame_count += 1
                person.fall_confidence = min(0.95, 0.6 + person.state_frame_count * 0.03)
                if person.state_frame_count >= self.confirmation_frames:
                    person.fall_state = FallState.FALL_CONFIRMED
                    person.fall_confidence = 1.0
                    person.state_frame_count = 0
                    fire_event = True
                    log_transition(FallState.FALL_CONFIRMED, f"posture != UPRIGHT for {self.confirmation_frames} frames")
            else:
                person.reset_fall_state()
                log_transition(FallState.NORMAL, "posture became UPRIGHT")

        elif state == FallState.POST_FALL_PENDING:
            # Detector temporarily lost person after strong fall evidence.
            # Progress confirmation using temporal evidence alone.
            person.state_frame_count += 1
            person.fall_confidence = min(0.95, 0.6 + person.state_frame_count * 0.03)
            if person.state_frame_count >= self.confirmation_frames:
                person.fall_state = FallState.FALL_CONFIRMED
                person.fall_confidence = 1.0
                person.state_frame_count = 0
                fire_event = True
                log_transition(FallState.FALL_CONFIRMED, "POST_FALL_PENDING timeout reached")

        elif state == FallState.FALL_CONFIRMED:
            # Retain until person physically stands back up (velocity <= 0 means they are not falling down anymore)
            if person.posture == Posture.UPRIGHT and current_velocity <= 0.0:
                person.reset_fall_state()
                log_transition(FallState.NORMAL, "posture UPRIGHT and upward velocity <= 0.0")

        return fire_event
