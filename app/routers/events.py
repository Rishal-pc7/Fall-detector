import json
import os
from fastapi import APIRouter

router = APIRouter()

@router.get("/events")
async def get_events(limit: int = 20):
    events_log_path = "data/events.json"
    if not os.path.exists(events_log_path):
        return []
        
    try:
        with open(events_log_path, 'r') as f:
            events = json.load(f)
            # Return newest first
            return list(reversed(events))[:limit]
    except json.JSONDecodeError:
        return []
