import pytest
from smartguard.detection.fall_detector import FallDetector
from smartguard.state.person_state import PersonState, FallState, Posture

@pytest.fixture
def detector():
    config = {
        "confirmation_frames": 5, # smaller for faster tests
        "possible_fall_frames": 2,
        "min_downward_velocity": 0.04,
        "min_vertical_displacement": 0.10,
        "torso_angle_threshold": 50,
        "aspect_ratio_threshold": 1.1
    }
    return FallDetector(config)

def test_fall_detector_standing(detector):
    person = PersonState(track_id=1)
    
    # Simulate standing (vertical bounding box, shoulders above hips)
    person.bbox = (100, 100, 150, 300) # w=50, h=200
    person.pose_available = True
    person.shoulder_center = (125, 120)
    person.hip_center = (125, 200)
    person.nose = (125, 100)
    
    for _ in range(10):
        fired = detector.update(person, 480, 640)
        assert not fired
        assert person.fall_state == FallState.NORMAL
        assert person.posture == Posture.UPRIGHT

def test_fall_detector_fall_sequence(detector):
    person = PersonState(track_id=2)
    
    # 1. Standing for 10 frames
    for i in range(10):
        person.bbox = (100, 100, 150, 300)
        person.pose_available = True
        person.shoulder_center = (125, 120)
        person.hip_center = (125, 200)
        person.nose = (125, 100)
        detector.update(person, 480, 640)
    
    assert person.fall_state == FallState.NORMAL
        
    # 2. Fast drop (high downward velocity)
    # y changes from 100 to 250 rapidly (0.3 of frame_h)
    person.bbox = (100, 250, 150, 450)
    person.nose = (125, 250)
    person.shoulder_center = (125, 270)
    person.hip_center = (125, 350)
    
    # Update for 2 frames to create velocity
    for i in range(2):
        detector.update(person, 480, 640)
        
    # Fall state should trigger due to high velocity + abnormal posture
    person.bbox = (100, 350, 300, 400) # horizontal now
    person.nose = (120, 360)
    person.shoulder_center = (150, 370)
    person.hip_center = (250, 370) # horizontal pose

    for i in range(5):
        detector.update(person, 480, 640)
        
    # After confirmation frames, it should be confirmed
    for i in range(detector.confirmation_frames + detector.possible_fall_frames + 2):
        detector.update(person, 480, 640)
        
    assert person.fall_state == FallState.FALL_CONFIRMED

def test_bbox_expansion_no_false_fall(detector):
    person = PersonState(track_id=3)
    
    # Person walking toward camera: bbox y1 stays roughly same, y2 increases rapidly
    # bbox bottom expands, but pose nose stays stable
    
    # Setup standing
    for i in range(10):
        person.bbox = (100, 100, 150, 200)
        person.pose_available = True
        person.nose = (125, 110)
        person.shoulder_center = (125, 130)
        person.hip_center = (125, 170)
        detector.update(person, 480, 640)
        
    # Expand bbox (walking forward)
    for i in range(5):
        person.bbox = (90, 100, 160, 200 + i*20) # y2 expands, y1 stable
        person.nose = (125, 110) # nose stable
        detector.update(person, 480, 640)
        
    # State should remain normal because pose velocity is ~0
    assert person.fall_state == FallState.NORMAL

def test_missing_pose_fallback(detector):
    person = PersonState(track_id=4)
    person.pose_available = False
    
    # Standing via bbox
    person.bbox = (100, 100, 150, 300) # ratio = 50/200 = 0.25 (UPRIGHT)
    detector.update(person, 480, 640)
    assert person.posture == Posture.UPRIGHT
    assert person.fall_state == FallState.NORMAL
    
    # Fall via bbox
    # Velocity creation
    for i in range(10):
        person.bbox = (100, 100, 150, 300)
        detector.update(person, 480, 640)
        
    person.bbox = (100, 350, 300, 400) # ratio = 200/50 = 4.0 (HORIZONTAL)
    for i in range(10):
        detector.update(person, 480, 640)
        
    assert person.posture == Posture.HORIZONTAL
    # Should trigger state transitions
    assert person.fall_state in (FallState.POSSIBLE_FALL, FallState.FALLING, FallState.FALL_CONFIRMED)
