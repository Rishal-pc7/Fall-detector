"""
Event Queue for asynchronous processing of Fall Events.

Handles the exact required sequence:
1. Write Firebase RTDB event (image_link = null)
2. Upload image to Firebase Storage
3. Update RTDB event with image_link
"""

import threading
import queue
import time
import logging

logger = logging.getLogger(__name__)

class EventQueue:
    def __init__(self, db_client, storage_client):
        self.db_client = db_client
        self.storage_client = storage_client
        
        self.queue = queue.Queue()
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)

    def push_event(self, event_id: str, timestamp: str, image_path: str):
        """Enqueue an event for processing."""
        task = {
            "event_id": event_id,
            "timestamp": timestamp,
            "image_path": image_path,
            "retries": 0
        }
        self.queue.put(task)
        logger.info(f"Event {event_id} queued for cloud processing")

    def _run_loop(self):
        while self.running:
            try:
                task = self.queue.get(timeout=1.0)
                
                event_id = task["event_id"]
                timestamp = task["timestamp"]
                image_path = task["image_path"]
                
                # 1. Realtime Database Write (INITIAL)
                db_success = self.db_client.create_fall_event(event_id, timestamp)
                
                if not db_success:
                    logger.error(f"Failed initial DB write for {event_id}. Retrying later.")
                    self._retry(task)
                    continue
                    
                # 2. Upload to Storage
                image_url = self.storage_client.upload_event_image(event_id, image_path)
                
                if not image_url:
                    logger.error(f"Failed Storage upload for {event_id}. Retrying later.")
                    # We still have the RTDB event with null link. 
                    # We will retry the upload.
                    self._retry(task)
                    continue
                    
                # 3. Update RTDB with image link
                update_success = self.db_client.update_image_link(event_id, image_url)
                
                if not update_success:
                    logger.error(f"Failed RTDB link update for {event_id}. Retrying later.")
                    self._retry(task)
                    continue
                    
                logger.info(f"Successfully processed event {event_id} through Cloud")
                self.queue.task_done()
                
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Unexpected error in event queue: {e}")

    def _retry(self, task):
        task["retries"] += 1
        if task["retries"] < 5:
            time.sleep(2) # Backoff
            self.queue.put(task)
        else:
            logger.error(f"Event {task['event_id']} permanently failed after 5 retries")
            self.queue.task_done()
