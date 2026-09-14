import cv2
import asyncio
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.get("/snapshot")
async def get_snapshot(request: Request):
    app_state = request.app.state.app_state
    
    with app_state.lock:
        frame = app_state.last_annotated_frame
        
    if frame is None:
        return Response(content="No frame available yet", status_code=503)
        
    ret, jpeg = cv2.imencode('.jpg', frame)
    if not ret:
        return Response(content="Failed to encode frame", status_code=500)
        
    return Response(content=jpeg.tobytes(), media_type="image/jpeg")

async def generate_frames(app_state):
    while True:
        with app_state.lock:
            frame = app_state.last_annotated_frame
            
        if frame is not None:
            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                # Yield the frame in MJPEG format
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        
        # Sleep briefly to not max out the CPU and run at ~20-30 FPS
        await asyncio.sleep(0.05)

@router.get("/stream")
async def get_stream(request: Request):
    """
    Returns a live MJPEG stream of the annotated camera feed.
    """
    app_state = request.app.state.app_state
    return StreamingResponse(generate_frames(app_state), media_type="multipart/x-mixed-replace; boundary=frame")
