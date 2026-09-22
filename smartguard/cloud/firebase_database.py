"""
Firebase Realtime Database implementation for SmartGuard.
"""

import json
import logging
import firebase_admin
from firebase_admin import credentials, db

logger = logging.getLogger(__name__)

class FirebaseDB:
    def __init__(self, service_account_json: str, database_url: str):
        self.connected = False
        if not service_account_json or not database_url:
            logger.warning("Firebase DB config missing.")
            return
            
        try:
            # Check if already initialized (in case of reloads)
            if not firebase_admin._apps:
                cred = credentials.Certificate(json.loads(service_account_json))
                firebase_admin.initialize_app(cred, {
                    'databaseURL': database_url
                })
            self.connected = True
            logger.info("Firebase Realtime Database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase DB: {e}")


    def create_fall_event(self, event_id: str, timestamp: str) -> bool:
        """
        Write initial event to RTDB with image_link = null.
        This MUST be called before uploading the image.
        """
        if not self.connected:
            return False
            
        try:
            ref = db.reference(f"fall_events/{event_id}")
            ref.set({
                "timestamp": timestamp,
                "image_link": None
            })
            return True
        except Exception as e:
            logger.error(f"Firebase RTDB set error: {e}")
            return False

    def update_image_link(self, event_id: str, image_url: str) -> bool:
        """
        Update ONLY the image_link field for an existing event.
        """
        if not self.connected:
            return False
            
        try:
            ref = db.reference(f"fall_events/{event_id}")
            ref.update({
                "image_link": image_url
            })
            return True
        except Exception as e:
            logger.error(f"Firebase RTDB update error: {e}")
            return False

    def get_fcm_tokens(self) -> list:
        """
        Fetch all registered FCM tokens.
        """
        if not self.connected:
            return []
            
        try:
            ref = db.reference("fcm_tokens")
            tokens_dict = ref.get()
            if tokens_dict and isinstance(tokens_dict, dict):
                return list(tokens_dict.keys())
            return []
        except Exception as e:
            logger.error(f"Failed to fetch FCM tokens: {e}")
            return []
