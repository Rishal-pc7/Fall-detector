import pytest
import os
import time
from unittest.mock import AsyncMock, patch, MagicMock
from app.alerts.alert_manager import AlertManager

@pytest.fixture
def mock_app_state():
    state = MagicMock()
    state.lock = MagicMock() # fake lock that acts as context manager
    state.lock.__enter__ = MagicMock()
    state.lock.__exit__ = MagicMock()
    return state

@pytest.mark.asyncio
async def test_alert_manager_cooldown(tmp_path, mock_app_state):
    events_path = os.path.join(tmp_path, "events.json")
    snapshots_path = os.path.join(tmp_path, "snapshots")
    manager = AlertManager(events_log_path=events_path, snapshot_dir=snapshots_path)
    
    frame = "fake_frame"
    
    with patch("app.alerts.alert_manager.cv2.imwrite") as mock_imwrite, \
         patch("app.alerts.alert_manager.send_alert", new_callable=AsyncMock) as mock_send_alert:
         
        mock_send_alert.return_value = True
        
        # Override config cooldown for test
        with patch("app.config.FALL_COOLDOWN_SECONDS", 2.0):
            # First alert should send
            sent1 = await manager.process_fall(mock_app_state, frame, "John", 0.9)
            assert sent1 is True
            assert mock_send_alert.call_count == 1
            
            # Second alert immediately after should be suppressed
            sent2 = await manager.process_fall(mock_app_state, frame, "John", 0.9)
            assert sent2 is False
            assert mock_send_alert.call_count == 1
            
            # Advance time inside manager
            manager.last_alert_time -= 3.0
            
            # Third alert should send
            sent3 = await manager.process_fall(mock_app_state, frame, "John", 0.9)
            assert sent3 is True
            assert mock_send_alert.call_count == 2
