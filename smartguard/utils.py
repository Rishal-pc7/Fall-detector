"""
Utility functions for SmartGuard.

Contains the position zone classifier, angle helpers, and other shared logic.
"""

import math
from typing import Tuple


# ── Position Zone Classification ──────────────────────────────────────────────

ZONE_NAMES = {
    (0, 0): "TOP_LEFT",
    (0, 1): "TOP_CENTER",
    (0, 2): "TOP_RIGHT",
    (1, 0): "CENTER_LEFT",
    (1, 1): "CENTER",
    (1, 2): "CENTER_RIGHT",
    (2, 0): "BOTTOM_LEFT",
    (2, 1): "BOTTOM_CENTER",
    (2, 2): "BOTTOM_RIGHT",
}


def compute_position(bbox: Tuple[int, int, int, int],
                     frame_w: int, frame_h: int) -> dict:
    """
    Compute fallen-person position from bounding box.

    Args:
        bbox: (x1, y1, x2, y2) in pixel coordinates.
        frame_w, frame_h: Frame dimensions.

    Returns:
        dict with center_x, center_y, ground_x, ground_y,
        normalized_x, normalized_y, position_zone.
    """
    x1, y1, x2, y2 = bbox

    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    ground_x = (x1 + x2) / 2
    ground_y = y2  # Bottom of bbox = estimated ground contact point

    norm_x = center_x / max(1, frame_w)
    norm_y = center_y / max(1, frame_h)

    # Classify into 3×3 zone grid
    col = min(2, int(norm_x * 3))
    row = min(2, int(norm_y * 3))
    zone = ZONE_NAMES.get((row, col), "CENTER")

    return {
        "center_x": round(center_x),
        "center_y": round(center_y),
        "ground_x": round(ground_x),
        "ground_y": round(ground_y),
        "normalized_x": round(norm_x, 3),
        "normalized_y": round(norm_y, 3),
        "position_zone": zone,
    }


def zone_to_servo_direction(zone: str) -> str:
    """
    Map a position zone to a servo direction for the Arduino.

    Returns 'left', 'center', or 'right'.
    """
    if "LEFT" in zone:
        return "left"
    elif "RIGHT" in zone:
        return "right"
    return "center"
