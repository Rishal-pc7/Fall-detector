"""
Firebase Storage implementation for SmartGuard.
"""

import logging
import firebase_admin
from firebase_admin import credentials, storage

logger = logging.getLogger(__name__)

class FirebaseStorage:
    def __init__(self, service_account_json: str, storage_bucket: str):
        self.connected = False
        self.bucket = None
        
        if not service_account_json or not storage_bucket:
            logger.warning("Firebase Storage config missing.")
            return
            
        try:
            # Assumes firebase_admin.initialize_app was already called by DB
            # We just need to get the bucket
            self.bucket = storage.bucket(storage_bucket)
            self.connected = True
            logger.info("Firebase Storage initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Storage: {e}")


    def upload_event_image(self, event_id: str, image_path: str) -> str:
        """
        Uploads an image to Firebase Storage and returns the public URL.
        Returns None on failure.
        """
        if not self.connected or not self.bucket:
            return None
            
        try:
            blob_path = f"fall_events/{event_id}.jpg"
            blob = self.bucket.blob(blob_path)
            blob.upload_from_filename(image_path)
            
            # Make the blob publicly accessible to get a standard URL
            # Note: requires Storage bucket to have appropriate permissions
            blob.make_public()
            return blob.public_url
        except Exception as e:
            logger.error(f"Firebase Storage upload error: {e}")
            return None
