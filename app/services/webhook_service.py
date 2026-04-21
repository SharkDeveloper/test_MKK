import httpx
import logging
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Service for sending webhook notifications to client URLs.
    Implements retry logic with exponential backoff.
    """
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    async def send_webhook(
        self, 
        url: str, 
        payment_id: str, 
        status: str, 
        amount: str, 
        currency: str,
        error_message: str | None = None
    ) -> bool:
        """
        Send a webhook notification with retry logic.
        
        Returns:
            True if webhook was sent successfully, False otherwise
        """
        payload = {
            "payment_id": payment_id,
            "status": status,
            "amount": amount,
            "currency": currency,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if error_message:
            payload["error"] = error_message
        
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    logger.info(f"Webhook sent successfully to {url} for payment {payment_id}")
                    return True
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"Webhook failed with status {e.response.status_code} "
                    f"(attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
            except httpx.RequestError as e:
                logger.warning(
                    f"Webhook request error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"Unexpected webhook error: {e}")
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
        
        logger.error(f"Failed to send webhook to {url} after {self.max_retries} attempts")
        return False
