import json
import os
import threading
import numpy as np
from typing import List, Tuple, Optional

class FaceDB:
    def __init__(self, file_path="data/faces.json"):
        self.file_path = file_path
        self.lock = threading.Lock()
        
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump({"people": {}}, f)
                
    def _read_db(self):
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"people": {}}
            
    def _write_db(self, data):
        with open(self.file_path, 'w') as f:
            json.dump(data, f)
            
    def enroll_person(self, name: str, embeddings: List[np.ndarray]):
        with self.lock:
            data = self._read_db()
            emb_lists = [emb.flatten().tolist() for emb in embeddings]
            if name not in data["people"]:
                data["people"][name] = []
            data["people"][name].extend(emb_lists)
            self._write_db(data)
            return len(data["people"][name])
            
    def get_all_embeddings(self) -> dict:
        with self.lock:
            data = self._read_db()
        result = {}
        for name, emb_lists in data.get("people", {}).items():
            result[name] = [np.array(e, dtype=np.float32).reshape(1, -1) for e in emb_lists]
        return result
        
    def match(self, recognizer, query_embedding, threshold=0.363) -> Tuple[Optional[str], float]:
        all_embeddings = self.get_all_embeddings()
        best_name = None
        best_score = 0.0
        
        for name, embeddings in all_embeddings.items():
            for stored_emb in embeddings:
                is_match, score = recognizer.match(query_embedding, stored_emb, threshold)
                if score > best_score:
                    best_score = score
                    if is_match:
                        best_name = name
                        
        if best_name is not None:
            return best_name, best_score
        return None, best_score
