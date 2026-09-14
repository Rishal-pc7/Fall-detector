"""
Unit tests for SmartGuard Per-Person Fall Detection State Machine.

Tests:
1. Full fall sequence: STANDING -> POSSIBLE_FALL -> FALLING -> FALL_CONFIRMED -> DOWN
2. Early recovery: STANDING -> POSSIBLE_FALL -> STANDING (false alarm cancelled)
3. Multi-person isolation: Person 1 falls while Person 2 remains standing.
"""

import pytest
from smartguard.state.person_state import PersonState, FallState
from smartguard.detection.fall_detector import FallDetector


@pytest.fixture
def detector():
    config = {
        "confirmation_frames": 5,
        "possible_fall_frames": 3,
        "torso_angle_threshold": 50,
        "fast_drop_threshold": 0.05,
        "aspect_ratio_threshold": 1.2
    }
    return FallDetector(config)


def test_full_fall_lifecycle(detector):
    person = PersonState(track_id=1)
    assert person.fall_state == FallState.STANDING

    frame_w, frame_h = 640, 480

    # 1. Person standing normally (w=100, h=300 -> aspect ratio 0.33, centered at y=200)
    for _ in range(5):
        person.bbox = (270, 50, 370, 350)
        detector.update(person, frame_h, frame_w)
        assert person.fall_state == FallState.STANDING

    # 2. Sudden drop & horizontal posture (w=300, h=100 -> aspect ratio 3.0, centroid drops to y=430)
    # This causes fast_drop > 0.05 and is_horizontal = True
    person.bbox = (170, 380, 470, 480)
    detector.update(person, frame_h, frame_w)
    assert person.fall_state == FallState.POSSIBLE_FALL

    # 3. Sustained for possible_fall_frames (3 frames) -> transitions to FALLING
    for _ in range(3):
        detector.update(person, frame_h, frame_w)
    assert person.fall_state == FallState.FALLING

    # 4. Sustained for confirmation_frames (5 frames) -> transitions to FALL_CONFIRMED and fires event
    fired_event = False
    for _ in range(6):
        if detector.update(person, frame_h, frame_w):
            fired_event = True

    assert fired_event is True

    # 5. After confirmed event, person remains DOWN on the floor
    assert person.fall_state == FallState.DOWN

    # 6. Person stands back up (vertical aspect ratio, angle goes back to 90)
    person.bbox = (270, 50, 370, 350)
    detector.update(person, frame_h, frame_w)
    assert person.fall_state == FallState.RECOVERING

    # 7. Sustained upright for 10 frames -> returns to STANDING
    for _ in range(10):
        detector.update(person, frame_h, frame_w)
    assert person.fall_state == FallState.STANDING


def test_early_recovery_aborts_fall(detector):
    person = PersonState(track_id=2)
    frame_w, frame_h = 640, 480

    # Normal standing
    for _ in range(5):
        person.bbox = (270, 50, 370, 350)
        detector.update(person, frame_h, frame_w)

    # Sudden momentary trip (possible fall)
    person.bbox = (170, 380, 470, 480)
    detector.update(person, frame_h, frame_w)
    assert person.fall_state == FallState.POSSIBLE_FALL

    # Immediately stands right back up before confirmation
    person.bbox = (270, 50, 370, 350)
    detector.update(person, frame_h, frame_w)
    assert person.fall_state == FallState.STANDING


def test_multi_person_state_isolation(detector):
    person1 = PersonState(track_id=1, name="Alice")
    person2 = PersonState(track_id=2, name="Bob")

    frame_w, frame_h = 640, 480

    # Person 1 standing history
    for _ in range(5):
        person1.bbox = (100, 50, 200, 350)
        person2.bbox = (400, 50, 500, 350)
        detector.update(person1, frame_h, frame_w)
        detector.update(person2, frame_h, frame_w)

    # Person 1 falls, Person 2 stays standing
    person1.bbox = (50, 380, 350, 480)
    person2.bbox = (400, 50, 500, 350)

    detector.update(person1, frame_h, frame_w)
    detector.update(person2, frame_h, frame_w)

    assert person1.fall_state == FallState.POSSIBLE_FALL
    assert person2.fall_state == FallState.STANDING
