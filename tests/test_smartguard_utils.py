"""
Unit tests for SmartGuard utility functions:
- Position calculation & 3x3 zone mapping
- Servo direction classification
"""

import pytest
from smartguard.utils import compute_position, zone_to_servo_direction, ZONE_NAMES


def test_compute_position_center():
    # Bounding box in the exact center of 600x600 frame
    bbox = (200, 200, 400, 400)
    pos = compute_position(bbox, frame_w=600, frame_h=600)

    assert pos["center_x"] == 300
    assert pos["center_y"] == 300
    assert pos["ground_x"] == 300
    assert pos["ground_y"] == 400
    assert pos["position_zone"] == "CENTER"
    assert zone_to_servo_direction(pos["position_zone"]) == "center"


def test_compute_position_bottom_left():
    # Bounding box in the bottom left
    bbox = (10, 450, 150, 580)
    pos = compute_position(bbox, frame_w=600, frame_h=600)

    assert pos["center_x"] == 80
    assert pos["center_y"] == 515
    assert pos["ground_y"] == 580
    assert pos["position_zone"] == "BOTTOM_LEFT"
    assert zone_to_servo_direction(pos["position_zone"]) == "left"


def test_compute_position_top_right():
    # Bounding box in the top right
    bbox = (450, 20, 580, 180)
    pos = compute_position(bbox, frame_w=600, frame_h=600)

    assert pos["position_zone"] == "TOP_RIGHT"
    assert zone_to_servo_direction(pos["position_zone"]) == "right"


def test_zone_mappings_complete():
    # Verify all 9 zones exist in ZONE_NAMES
    expected_zones = {
        "TOP_LEFT", "TOP_CENTER", "TOP_RIGHT",
        "CENTER_LEFT", "CENTER", "CENTER_RIGHT",
        "BOTTOM_LEFT", "BOTTOM_CENTER", "BOTTOM_RIGHT"
    }
    assert set(ZONE_NAMES.values()) == expected_zones
