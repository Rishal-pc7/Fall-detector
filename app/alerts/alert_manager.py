import time
import os
import json
import logging
import cv2
import asyncio
from datetime import datetime
from app import config
from app.alerts.telegram_client import send_alert

logger = logging.getLogger(__name__)

class AlertManager:
    def __init__(self, events_log_path="data/events.json", snapshot_dir="data/snapshots"):
        self.events_log_path = events_log_path
        self.snapshot_dir = snapshot_dir
        self.last_alert_time = 0.0
        
        os.makedirs(os.path.dirname(self.events_log_path), exist_ok=True)
        os.makedirs(self.snapshot_dir, exist_ok=True)
        
        if not os.path.exists(self.events_log_path):
            with open(self.events_log_path, 'w') as f:
                json.dump([], f)
                
    def _log_event(self, event_data):
        try:
            with open(self.events_log_path, 'r') as f:
                events = json.load(f)
        except json.JSONDecodeError:
            events = []
            
        events.append(event_data)
        
        with open(self.events_log_path, 'w') as f:
            json.dump(events, f)
            
    async def process_fall(self, app_state, frame, person_name: str, confidence: float):
        """
        Global cooldown logic and processing of fall event.
        Returns True if alert was sent, False if cooldown suppressed it.
        """
        current_time = time.time()
        time_since_last = current_time - self.last_alert_time
        
        if time_since_last < config.FALL_COOLDOWN_SECONDS:
            logger.info(f"Fall detected ({person_name}), but suppressed by cooldown ({time_since_last:.1f}s < {config.FALL_COOLDOWN_SECONDS}s)")
            alert_sent = False
        else:
            alert_sent = True
            self.last_alert_time = current_time
            
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_filename = f"fall_{timestamp_str}.jpg"
        snapshot_path = os.path.join(self.snapshot_dir, snapshot_filename)
        
        # Save snapshot
        cv2.imwrite(snapshot_path, frame)
        
        # Prepare event data
        event_id = f"evt_{timestamp_str}"
        event_data = {
            "id": event_id,
            "timestamp": datetime.now().isoformat(),
            "person": person_name,
            "confidence": float(confidence),
            "snapshot_path": snapshot_path,
            "alert_sent": alert_sent
        }
        
        # Save to AppState
        with app_state.lock:
            app_state.last_fall_event = event_data
            
        # Log to JSON
        self._log_event(event_data)
        
        if alert_sent:
            caption = f"⚠️ FALL DETECTED ⚠️\nPerson: {person_name}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            # send_alert is async, so we await it
            success = await send_alert(snapshot_path, caption)
            if not success:
                logger.error("Failed to deliver Telegram alert")
                
        return alert_sent
