"""
Event Manager for creating and dispatching fall events locally.
"""

import os
import cv2
import json
import logging
from datetime import datetime
from smartguard.state.person_state import PersonState

logger = logging.getLogger(__name__)

class EventManager:
    def __init__(self, config, arduino_client, event_queue):
        self.local_log_path = config["events"]["local_log_path"]
        self.snapshot_dir = config["events"]["snapshot_dir"]
        self.arduino_client = arduino_client
        self.event_queue = event_queue
        
        os.makedirs(os.path.dirname(self.local_log_path), exist_ok=True)
        os.makedirs(self.snapshot_dir, exist_ok=True)
        
        if not os.path.exists(self.local_log_path):
            with open(self.local_log_path, 'w') as f:
                json.dump([], f)

    def handle_fall_confirmed(self, person: PersonState, frame):
        """
        Called by pipeline when a person transitions to FALL_CONFIRMED.
        """
        current_time = datetime.now()
        timestamp_str = current_time.strftime("%Y-%m-%dT%H:%M:%S")
        timestamp_safe = current_time.strftime("%Y%m%d_%H%M%S")
        
        event_id = f"evt_{timestamp_safe}_{person.track_id}"
        
        # 1. Capture snapshot
        snapshot_filename = f"{event_id}.jpg"
        snapshot_path = os.path.join(self.snapshot_dir, snapshot_filename)
        cv2.imwrite(snapshot_path, frame)
        
        # 2. Local Diagnostic Log (RICH data)
        event_data = {
            "event_id": event_id,
            "timestamp": timestamp_str,
            "track_id": person.track_id,
            "fall_confidence": person.fall_confidence,
            "body_angle": person.body_angle,
            "center_x": person.center_x,
            "center_y": person.center_y,
            "position_zone": person.position_zone,
            "snapshot_path": snapshot_path
        }
        self._log_local(event_data)
        
        # 3. Hardware (Arduino) command
        self.arduino_client.send_fall_event(
            angle=person.body_angle,
            x=person.center_x,
            y=person.center_y
        )
        
        # 4. Cloud processing (MINIMAL data)
        self.event_queue.push_event(
            event_id=event_id,
            timestamp=timestamp_str,
            image_path=snapshot_path
        )
        
        logger.info(f"Fall event {event_id} created")
        return event_data

    def _log_local(self, event_data):
        try:
            with open(self.local_log_path, 'r') as f:
                events = json.load(f)
        except json.JSONDecodeError:
            events = []
            
        events.append(event_data)
        
        with open(self.local_log_path, 'w') as f:
            json.dump(events, f)
