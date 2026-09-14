"""
Global thread-safe application state for SmartGuard.

Shared between the CV pipeline thread, the event processing thread,
the Arduino thread, and the Pygame UI thread.
"""

import threading
import time
import numpy as np
from typing import Dict, Optional

from smartguard.state.person_state import PersonState


class AppState:
    """
    Thread-safe container for all shared runtime data.

    Every read/write from outside the owning thread must happen
    under self.lock. Keep critical sections short.
    """

    def __init__(self):
        self.lock = threading.Lock()

        # ── Camera ────────────────────────────────────────────────────────
        self.current_frame: Optional[np.ndarray] = None
        self.annotated_frame: Optional[np.ndarray] = None
        self.camera_connected: bool = False

        # ── Per-person tracking state ─────────────────────────────────────
        # Dict[track_id -> PersonState]
        self.people: Dict[int, PersonState] = {}

        # ── Hardware / cloud status ───────────────────────────────────────
        self.arduino_connected: bool = False
        self.firebase_connected: bool = False
        self.storage_connected: bool = False

        # ── Last fall event (for quick UI display) ────────────────────────
        self.last_fall_event: Optional[dict] = None

        # ── Timing ────────────────────────────────────────────────────────
        self.start_time: float = time.time()
        self.fps: float = 0.0
        self.system_status: str = "initializing"

    # ── Convenience helpers (always acquire lock internally) ──────────────

    def get_or_create_person(self, track_id: int) -> PersonState:
        """Get existing PersonState or create a new one for this track_id."""
        with self.lock:
            if track_id not in self.people:
                self.people[track_id] = PersonState(track_id=track_id)
            return self.people[track_id]

    def remove_stale_tracks(self, active_ids: set):
        """Remove PersonState entries for tracks no longer visible."""
        with self.lock:
            stale = [tid for tid in self.people if tid not in active_ids]
            for tid in stale:
                del self.people[tid]

    def get_all_people(self) -> Dict[int, PersonState]:
        """Return a shallow copy of the people dict for safe iteration."""
        with self.lock:
            return dict(self.people)

    def get_status_summary(self) -> dict:
        with self.lock:
            return {
                "camera": self.camera_connected,
                "arduino": self.arduino_connected,
                "firebase": self.firebase_connected,
                "storage": self.storage_connected,
                "people_count": len(self.people),
                "fps": round(self.fps, 1),
                "uptime": round(time.time() - self.start_time, 1),
                "status": self.system_status,
            }
