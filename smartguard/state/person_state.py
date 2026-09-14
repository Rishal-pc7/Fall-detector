"""
Per-person state management for SmartGuard.

Every tracked person gets their own PersonState instance, ensuring independent
fall detection, recognition, and event handling. This is the core data structure
that prevents the "single global fall_detected = True" anti-pattern.
"""

import time
import collections
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Tuple


class Posture(Enum):
    """
    Static classification of a person's current posture, completely independent
    of whether they are falling.
    """
    UPRIGHT = "UPRIGHT"
    SEATED = "SEATED"
    HORIZONTAL = "HORIZONTAL"


class FallState(Enum):
    """
    Explicit state machine for temporal fall detection.
    This tracks the event of a fall, not the static posture.

    Transitions:
        NORMAL → POSSIBLE_FALL    : rapid downward motion + orientation change
        POSSIBLE_FALL → FALLING   : conditions sustained for N frames
        FALLING → FALL_CONFIRMED  : abnormal state sustained for confirmation period
        FALLING → POST_FALL_PENDING : detector temporarily lost track immediately after fall
    """
    NORMAL = "NORMAL"
    POSSIBLE_FALL = "POSSIBLE_FALL"
    FALLING = "FALLING"
    POST_FALL_PENDING = "POST_FALL_PENDING"
    FALL_CONFIRMED = "FALL_CONFIRMED"


@dataclass
class PersonState:
    """
    Independent state for a single tracked person.

    Each field is updated per-frame by the pipeline. The UI reads these
    values to decide what to render (bounding box vs fall alert overlay).
    """
    track_id: int

    # ── Bounding box (pixel coords, updated every frame) ──────────────────
    bbox: Optional[Tuple[int, int, int, int]] = None  # (x1, y1, x2, y2)

    # ── Pose Estimation ───────────────────────────────────────────────────
    pose_available: bool = False
    pose_confidence: float = 0.0
    
    # Keypoints: (x, y, conf)
    nose: Optional[Tuple[int, int, float]] = None
    left_shoulder: Optional[Tuple[int, int, float]] = None
    right_shoulder: Optional[Tuple[int, int, float]] = None
    left_hip: Optional[Tuple[int, int, float]] = None
    right_hip: Optional[Tuple[int, int, float]] = None
    left_knee: Optional[Tuple[int, int, float]] = None
    right_knee: Optional[Tuple[int, int, float]] = None
    left_ankle: Optional[Tuple[int, int, float]] = None
    right_ankle: Optional[Tuple[int, int, float]] = None

    # Derived pose features
    shoulder_center: Optional[Tuple[int, int]] = None
    hip_center: Optional[Tuple[int, int]] = None
    pose_torso_angle: float = 90.0

    # ── Static Posture ────────────────────────────────────────────────────
    posture: Posture = field(default=Posture.UPRIGHT)

    # ── Fall detection ────────────────────────────────────────────────────
    fall_state: FallState = field(default=FallState.NORMAL)
    fall_confidence: float = 0.0

    # Counts how many consecutive frames the current transitional condition
    # has been met. Reset to 0 on state change.
    state_frame_count: int = 0

    # ── Post-fall state persistence ───────────────────────────────────────
    post_fall_timer_start: float = 0.0
    last_known_snapshot: Optional[dict] = None
    reason_for_track_loss: str = ""

    # ── Body / fall angle ─────────────────────────────────────────────────
    # Convention: 90° = upright/vertical, 0° = horizontal/lying flat.
    body_angle: float = 90.0

    # ── Fallen-person position (only meaningful when falling/down) ────────
    center_x: float = 0.0
    center_y: float = 0.0
    ground_x: float = 0.0
    ground_y: float = 0.0
    normalized_x: float = 0.5
    normalized_y: float = 0.5
    position_zone: str = "CENTER"

    # ── Per-person event cooldown ─────────────────────────────────────────
    last_event_time: float = 0.0
    event_created: bool = False  # True once FALL_CONFIRMED event is dispatched

    # ── Rolling history windows (for temporal fall detection) ─────────────
    centroid_y_history: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=30)
    )
    head_y_history: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=30)
    )
    nose_y_history: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=30)
    )
    shoulder_y_history: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=30)
    )
    angle_history: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=30)
    )
    pose_torso_angle_history: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=30)
    )

    # ── MediaPipe pose landmarks (Legacy/if available) ────────────────────
    pose_landmarks: object = field(default=None, repr=False)

    def reset_fall_state(self):
        """Reset fall tracking when person recovers to normal."""
        self.fall_state = FallState.NORMAL
        self.fall_confidence = 0.0
        self.state_frame_count = 0
        self.event_created = False

    @property
    def is_falling(self) -> bool:
        """True if person is in any active fall event state."""
        return self.fall_state != FallState.NORMAL

    @property
    def is_normal(self) -> bool:
        return self.fall_state == FallState.NORMAL
