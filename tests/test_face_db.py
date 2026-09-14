import pytest
import os
import json
import numpy as np
try:
    from smartguard.recognition.face_db import FaceDB
except ImportError:
    from app.recognition.face_db import FaceDB

def test_face_db_enroll_and_get(tmp_path):
    db_path = os.path.join(tmp_path, "faces.json")
    db = FaceDB(file_path=db_path)
    
    emb1 = np.array([0.1, 0.2, 0.3])
    emb2 = np.array([0.4, 0.5, 0.6])
    
    # Enroll
    count = db.enroll_person("John", [emb1, emb2])
    assert count == 2
    
    # Get
    all_embs = db.get_all_embeddings()
    assert "John" in all_embs
    assert len(all_embs["John"]) == 2
    assert np.allclose(all_embs["John"][0], emb1)

def test_face_db_corrupted_recovery(tmp_path):
    db_path = os.path.join(tmp_path, "faces.json")
    with open(db_path, 'w') as f:
        f.write("corrupted json {")
        
    db = FaceDB(file_path=db_path)
    all_embs = db.get_all_embeddings()
    assert len(all_embs) == 0 # Recovers gracefully
