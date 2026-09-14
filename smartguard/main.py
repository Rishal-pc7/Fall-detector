"""
SmartGuard Main Entry Point.

Starts all background threads:
- Arduino Serial Controller
- Firebase Cloud Event Queue
- Camera Capture Thread
- Computer Vision Pipeline Thread
And runs the Pygame Dashboard on the main GUI thread.
"""

import os
import sys
import logging
import signal

from smartguard.config.settings import (
    CONFIG,
    CAMERA_INDEX,
    CAMERA_BACKEND,
    ARDUINO_PORT,
    ARDUINO_BAUD,
    FIREBASE_SERVICE_ACCOUNT_JSON,
    FIREBASE_DATABASE_URL,
    FIREBASE_STORAGE_BUCKET,
)
from smartguard.state.app_state import AppState
from smartguard.hardware.arduino_controller import ArduinoController
from smartguard.cloud.firebase_database import FirebaseDB
from smartguard.cloud.firebase_storage import FirebaseStorage
from smartguard.events.event_queue import EventQueue
from smartguard.events.event_manager import EventManager
from smartguard.camera.camera_manager import CameraManager
from smartguard.pipeline import SmartGuardPipeline
from smartguard.ui.pygame_dashboard import PygameDashboard

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("SmartGuard")


def main():
    logger.info("Initializing SmartGuard Multi-Person Fall Detection System...")

    # 1. Thread-safe Global State
    app_state = AppState()

    # 2. Hardware: Arduino Serial Controller
    arduino = ArduinoController(port=ARDUINO_PORT, baudrate=ARDUINO_BAUD)
    arduino.start()
    with app_state.lock:
        app_state.arduino_connected = arduino.connected

    # 3. Cloud: Firebase Realtime Database & Storage
    firebase_db = FirebaseDB(
        service_account_json=FIREBASE_SERVICE_ACCOUNT_JSON,
        database_url=FIREBASE_DATABASE_URL
    )
    firebase_storage = FirebaseStorage(
        service_account_json=FIREBASE_SERVICE_ACCOUNT_JSON,
        storage_bucket=FIREBASE_STORAGE_BUCKET
    )
    with app_state.lock:
        app_state.firebase_connected = firebase_db.connected
        app_state.storage_connected = firebase_storage.connected

    # 4. Asynchronous Cloud Event Queue
    event_queue = EventQueue(db_client=firebase_db, storage_client=firebase_storage)
    event_queue.start()

    # 5. Local Event Manager (coordinates local logging, Arduino pan, and Cloud queue)
    event_manager = EventManager(
        config=CONFIG,
        arduino_client=arduino,
        event_queue=event_queue
    )

    # 6. Threaded Camera Capture
    cam_cfg = CONFIG.get("camera", {})
    cam_width = cam_cfg.get("width", 640)
    cam_height = cam_cfg.get("height", 480)
    camera = CameraManager(
        camera_index=CAMERA_INDEX,
        app_state=app_state,
        width=cam_width,
        height=cam_height,
        backend=CAMERA_BACKEND
    )
    camera.start()

    # 7. Computer Vision Processing Pipeline
    pipeline = SmartGuardPipeline(
        app_state=app_state,
        config=CONFIG,
        event_manager=event_manager
    )
    pipeline.start()

    # 8. Main Thread: Pygame Dashboard UI
    dashboard = PygameDashboard(app_state=app_state, config=CONFIG)

    def shutdown_all(*args):
        logger.info("Shutting down SmartGuard system components...")
        dashboard.running = False
        pipeline.stop()
        camera.stop()
        event_queue.stop()
        arduino.stop()
        logger.info("SmartGuard shutdown complete.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_all)

    try:
        dashboard.run()
    except Exception as e:
        import traceback
        logger.error(f"Error during UI execution: {e}")
        logger.error(traceback.format_exc())
    finally:
        shutdown_all()


if __name__ == "__main__":
    main()
