import pytest
import httpx
from unittest.mock import AsyncMock, patch
from app.actuation.servo_client import send_pan_angle

@pytest.mark.asyncio
async def test_send_pan_angle_clamp():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # Should clamp to 170
        angle = await send_pan_angle(200)
        assert angle == 170
        
        # Should clamp to 10
        angle = await send_pan_angle(0)
        assert angle == 10

@pytest.mark.asyncio
async def test_send_pan_angle_debounce():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # Requesting 92 when last was 90 should be ignored (returns 90)
        angle = await send_pan_angle(92, last_sent_angle=90)
        assert angle == 90
        assert mock_post.call_count == 0

@pytest.mark.asyncio
async def test_send_pan_angle_success():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        angle = await send_pan_angle(120, last_sent_angle=90)
        assert angle == 120
        assert mock_post.call_count == 1
