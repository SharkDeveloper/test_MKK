import asyncio
import random
from datetime import datetime

from app.models import PaymentStatus


class PaymentGateway:
    """
    Emulates an external payment gateway.
    - Processing delay: 2-5 seconds
    - Success rate: 90%
    - Failure rate: 10%
    """
    
    def __init__(self, success_rate: float = 0.9, min_delay: int = 2, max_delay: int = 5):
        self.success_rate = success_rate
        self.min_delay = min_delay
        self.max_delay = max_delay
    
    async def process_payment(self, payment_id: str, amount: str, currency: str) -> tuple[PaymentStatus, str | None]:
        """
        Process a payment through the gateway.
        
        Returns:
            Tuple of (status, error_message)
        """
        # Simulate processing delay
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)
        
        # Simulate success/failure
        if random.random() < self.success_rate:
            return PaymentStatus.SUCCEEDED, None
        else:
            error_messages = [
                "Insufficient funds",
                "Card declined",
                "Invalid card number",
                "Transaction timeout",
                "Fraud detection triggered",
            ]
            error = random.choice(error_messages)
            return PaymentStatus.FAILED, error
