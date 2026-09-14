import httpx
import logging
from app import config

logger = logging.getLogger(__name__)

async def send_pan_angle(angle: int, last_sent_angle: int = None) -> int:
    """
    Sends pan angle to ESP32. Clamps to [10, 170].
    Returns the angle that was sent (or attempted to be sent).
    """
    # Clamp angle
    angle = max(10, min(170, int(angle)))
    
    # Debounce
    if last_sent_angle is not None and abs(angle - last_sent_angle) < 3:
        return last_sent_angle
        
    url = f"{config.ESP32_BASE_URL}/pan"
    payload = {"angle": angle}
    
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.RequestError as e:
        logger.warning(f"Failed to communicate with ESP32 at {url}: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error when sending pan angle: {e}")
        
    return angle
