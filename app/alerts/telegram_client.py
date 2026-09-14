import httpx
import logging
from app import config

logger = logging.getLogger(__name__)

async def send_alert(photo_path: str, caption: str) -> bool:
    """
    Sends an alert with a photo to the configured Telegram chat.
    Returns True if successful, False otherwise.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials missing, skipping alert.")
        return False
        
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendPhoto"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            with open(photo_path, 'rb') as photo:
                files = {'photo': photo}
                data = {'chat_id': config.TELEGRAM_CHAT_ID, 'caption': caption}
                response = await client.post(url, data=data, files=files)
                response.raise_for_status()
                return True
    except httpx.RequestError as e:
        logger.error(f"Telegram network error: {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Telegram API error: {e.response.text}")
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")
        
    return False
