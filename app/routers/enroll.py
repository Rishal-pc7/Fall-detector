import cv2
import numpy as np
from typing import List
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException

router = APIRouter()

@router.post("/enroll")
async def enroll_person(
    request: Request,
    name: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """
    Enrolls a person by taking multiple images, detecting their face, and storing embeddings.
    """
    face_detector = request.app.state.face_detector
    face_recognizer = request.app.state.face_recognizer
    face_db = request.app.state.face_db
    
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 images allowed")
        
    embeddings = []
    
    for file in files:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            continue
            
        faces = face_detector.detect(img)
        if len(faces) == 0:
            continue # No face found in this image
            
        # Use the most confident face or the largest one. Here we take the first.
        face = faces[0]
        
        aligned_face = face_recognizer.align_crop(img, face)
        feature = face_recognizer.feature(aligned_face)
        embeddings.append(feature)
        
    if not embeddings:
        raise HTTPException(status_code=400, detail="No faces detected in any of the provided images.")
        
    num_stored = face_db.enroll_person(name, embeddings)
    
    return {"status": "ok", "name": name, "num_embeddings_stored": num_stored}
