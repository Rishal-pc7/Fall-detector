"""
trigger_dummy_fall.py

Quick test script to fire a fake fall event end-to-end:
  1. Writes event to Firebase RTDB (image_link = null)
  2. Sends FCM push notification to all registered devices
  3. Uploads a dummy black-frame snapshot to Firebase Storage
  4. Updates RTDB event with the image link

Usage (from repo root, with venv activated):
  python trigger_dummy_fall.py
"""

import os
import sys
import logging
from datetime import datetime

from dotenv import load_dotenv
import numpy as np
import cv2

# -- Bootstrap
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("dummy_fall")

# -- Read env vars
SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
DATABASE_URL         = os.getenv("FIREBASE_DATABASE_URL")
STORAGE_BUCKET       = os.getenv("FIREBASE_STORAGE_BUCKET")

if not all([SERVICE_ACCOUNT_JSON, DATABASE_URL, STORAGE_BUCKET]):
    logger.error("Missing Firebase env vars. Make sure .env is configured correctly.")
    sys.exit(1)

# -- Init Firebase clients
from smartguard.cloud.firebase_database import FirebaseDB
from smartguard.cloud.firebase_storage import FirebaseStorage

db_client      = FirebaseDB(SERVICE_ACCOUNT_JSON, DATABASE_URL)
storage_client = FirebaseStorage(SERVICE_ACCOUNT_JSON, STORAGE_BUCKET)

if not db_client.connected:
    logger.error("FirebaseDB failed to connect. Check credentials.")
    sys.exit(1)

# -- Generate a dummy event
current_time   = datetime.now()
timestamp_str  = current_time.strftime("%Y-%m-%dT%H:%M:%S")
timestamp_safe = current_time.strftime("%Y%m%d_%H%M%S")
event_id       = f"evt_DUMMY_{timestamp_safe}_track0"

logger.info(f"Triggering dummy fall event: {event_id}")

# -- Step 1: Write RTDB event
logger.info("Step 1 - Writing initial event to RTDB...")
db_success = db_client.create_fall_event(event_id, timestamp_str)
if not db_success:
    logger.error("RTDB write failed. Aborting.")
    sys.exit(1)
logger.info("  RTDB event created (image_link = null)")

# -- Step 2: Send FCM notification
logger.info("Step 2 - Sending FCM notification...")
try:
    from firebase_admin import messaging
    fcm_tokens = db_client.get_fcm_tokens()
    if fcm_tokens:
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title="SmartGuard Fall Alert [TEST]",
                body=f"Dummy fall detected at {timestamp_str}"
            ),
            tokens=fcm_tokens,
        )
        response = messaging.send_multicast(message)
        logger.info(f"  FCM sent to {len(fcm_tokens)} device(s). Success: {response.success_count}, Failure: {response.failure_count}")
    else:
        logger.warning("  No FCM tokens registered. Open the Flutter app on a device first.")
except Exception as e:
    logger.error(f"  FCM failed: {e}")

# -- Step 3: Create and upload dummy snapshot
logger.info("Step 3 - Uploading dummy snapshot to Storage...")
snapshot_dir = "data/events/snapshots"
os.makedirs(snapshot_dir, exist_ok=True)

dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
cv2.putText(dummy_frame, "DUMMY FALL EVENT", (100, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
cv2.putText(dummy_frame, timestamp_str, (130, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)

snapshot_path = os.path.join(snapshot_dir, f"{event_id}.jpg")
cv2.imwrite(snapshot_path, dummy_frame)
logger.info(f"  Dummy snapshot saved: {snapshot_path}")

image_url = storage_client.upload_event_image(event_id, snapshot_path)
if image_url:
    logger.info(f"  Uploaded to Storage: {image_url}")
else:
    logger.warning("  Storage upload failed. RTDB event will have no image link.")

# -- Step 4: Update RTDB with image link
if image_url:
    logger.info("Step 4 - Updating RTDB event with image link...")
    update_success = db_client.update_image_link(event_id, image_url)
    if update_success:
        logger.info("  image_link updated in RTDB")
    else:
        logger.error("  Failed to update image_link")

# -- Done
logger.info("")
logger.info("--- Dummy Fall Test Complete ---")
logger.info(f"  Event ID   : {event_id}")
logger.info(f"  Timestamp  : {timestamp_str}")
logger.info(f"  Image URL  : {image_url or 'N/A'}")
logger.info("Check your Firebase console and phone for the notification!")
