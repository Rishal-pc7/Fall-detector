from contextlib import asynccontextmanager
from fastapi import FastAPI

from app import config
from app.state import AppState
from app.camera.capture import VideoCaptureThread
from app.detection.person_detector import PersonDetector
from app.detection.fall_detector import FallDetector
from app.recognition.face_detector_yunet import FaceDetectorYuNet
from app.recognition.face_recognizer import FaceRecognizerSFace
from app.recognition.face_db import FaceDB
from app.alerts.alert_manager import AlertManager
from app.pipeline import MainLoop

from app.routers import status, snapshot, events, enroll

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize state and components
    app.state.app_state = AppState()
    
    app.state.person_detector = PersonDetector()
    app.state.fall_detector = FallDetector()
    
    app.state.face_detector = FaceDetectorYuNet(model_path=config.YUNET_MODEL_PATH)
    app.state.face_recognizer = FaceRecognizerSFace(model_path=config.SFACE_MODEL_PATH)
    app.state.face_db = FaceDB()
    
    app.state.alert_manager = AlertManager()
    
    app.state.capture_thread = VideoCaptureThread(config.CAMERA_INDEX, app.state.app_state)
    app.state.main_loop = MainLoop(
        app.state.app_state,
        app.state.person_detector,
        app.state.fall_detector,
        app.state.face_detector,
        app.state.face_recognizer,
        app.state.face_db,
        app.state.alert_manager
    )
    
    # Start threads
    app.state.capture_thread.start()
    app.state.main_loop.start()
    
    yield
    
    # Stop threads
    app.state.main_loop.stop()
    app.state.capture_thread.stop()

app = FastAPI(title="Fall Detection Backend", lifespan=lifespan)

# Mount routers
app.include_router(status.router)
app.include_router(snapshot.router)
app.include_router(events.router)
app.include_router(enroll.router)
