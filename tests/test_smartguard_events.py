"""
Unit tests for Event Manager and Event Queue.
"""

import os
import json
import tempfile
import numpy as np
import pytest
from unittest.mock import MagicMock

from smartguard.state.person_state import PersonState, FallState
from smartguard.events.event_manager import EventManager
from smartguard.events.event_queue import EventQueue


@pytest.fixture
def temp_event_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "events.json")
        snap_dir = os.path.join(tmpdir, "snapshots")
        config = {
            "events": {
                "local_log_path": log_path,
                "snapshot_dir": snap_dir
            }
        }
        yield config, log_path, snap_dir


def test_event_manager_creates_local_records(temp_event_env):
    config, log_path, snap_dir = temp_event_env

    mock_arduino = MagicMock()
    mock_queue = MagicMock()

    manager = EventManager(config, mock_arduino, mock_queue)

    person = PersonState(
        track_id=7,
        name="Alex",
        recognition_confidence=0.88,
        fall_confidence=0.95,
        body_angle=18.5,
        center_x=320,
        center_y=420,
        position_zone="BOTTOM_CENTER"
    )
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    event_data = manager.handle_fall_confirmed(person, fake_frame)

    # 1. Assert return data
    assert event_data["person_name"] == "Alex"
    assert event_data["track_id"] == 7
    assert event_data["body_angle"] == 18.5
    assert os.path.exists(event_data["snapshot_path"])

    # 2. Assert Arduino was commanded
    mock_arduino.send_fall_event.assert_called_once_with(
        angle=18.5,
        x=320,
        y=420
    )

    # 3. Assert EventQueue was pushed to
    mock_queue.push_event.assert_called_once()

    # 4. Assert local JSON log was updated
    with open(log_path, "r") as f:
        logs = json.load(f)
    assert len(logs) == 1
    assert logs[0]["person_name"] == "Alex"
