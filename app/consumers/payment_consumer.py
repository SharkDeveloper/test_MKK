import asyncio
import logging
from datetime import datetime
from typing import Annotated

from faststream.rabbit import RabbitBroker, RabbitMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.session import engine, async_session_maker
from app.models import PaymentStatus, OutboxMessage
from app.services.payment_gateway import PaymentGateway
from app.services.webhook_service import WebhookService
from app.services.payment_service import PaymentService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


broker = RabbitBroker(settings.rabbit_url)

# Declare queues and exchanges
PAYMENTS_EXCHANGE = "payments"
PAYMENTS_NEW_QUEUE = "payments.new"
PAYMENTS_DLQ_QUEUE = "payments.dlq"


async def get_session() -> AsyncSession:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        yield session


async def process_payment(
    payment_id: str,
    amount: str,
    currency: str,
    webhook_url: str | None,
    db: AsyncSession,
) -> None:
    """
    Process a single payment.
    
    - Emulates payment gateway processing (2-5 sec, 90% success)
    - Updates payment status in DB
    - Sends webhook notification with retry logic
    """
    logger.info(f"Processing payment {payment_id}...")
    
    service = PaymentService(db)
    gateway = PaymentGateway(
        success_rate=settings.payment_success_rate,
        min_delay=settings.payment_processing_delay_min,
        max_delay=settings.payment_processing_delay_max,
    )
    webhook_service = WebhookService(
        max_retries=settings.max_retries,
        base_delay=settings.retry_base_delay,
    )
    
    # Process payment through gateway
    status, error_message = await gateway.process_payment(payment_id, amount, currency)
    
    # Update payment status in DB
    updated_payment = await service.update_payment_status(payment_id, status)
    
    if not updated_payment:
        logger.error(f"Payment {payment_id} not found for status update")
        return
    
    logger.info(f"Payment {payment_id} status updated to {status}")
    
    # Send webhook notification if URL provided
    if webhook_url:
        success = await webhook_service.send_webhook(
            url=webhook_url,
            payment_id=payment_id,
            status=status.value,
            amount=amount,
            currency=currency,
            error_message=error_message,
        )
        
        if success:
            logger.info(f"Webhook sent successfully for payment {payment_id}")
        else:
            logger.warning(f"Failed to send webhook for payment {payment_id} after retries")
    
    # Create outbox message for payment completed event
    await service.create_outbox_message(
        event_type="payment.completed",
        payload={
            "payment_id": payment_id,
            "status": status.value,
            "processed_at": datetime.utcnow().isoformat(),
            "error_message": error_message,
        }
    )


@broker.subscriber(
    PAYMENTS_NEW_QUEUE,
    exchange=PAYMENTS_EXCHANGE,
)
async def process_payment_message(message: dict) -> None:
    """
    Consumer for processing new payment messages.
    """
    payment_id = message.get("payment_id")
    amount = message.get("amount")
    currency = message.get("currency")
    webhook_url = message.get("webhook_url")
    
    async with async_session_maker() as db:
        await process_payment(payment_id, amount, currency, webhook_url, db)


async def publish_outbox_messages() -> None:
    """
    Background task to publish unpublished outbox messages to RabbitMQ.
    Implements the Outbox pattern for guaranteed event delivery.
    """
    async with async_session_maker() as db:
        service = PaymentService(db)
        messages = await service.get_unpublished_outbox_messages(limit=100)
        
        for msg in messages:
            try:
                await broker.publish(
                    msg.payload,
                    PAYMENTS_NEW_QUEUE,
                    exchange=PAYMENTS_EXCHANGE,
                )
                await service.mark_outbox_published(msg.id)
                logger.info(f"Published outbox message {msg.id} ({msg.event_type})")
            except Exception as e:
                logger.error(f"Failed to publish outbox message {msg.id}: {e}")


async def publish_outbox_messages_loop() -> None:
    """Periodically check and publish outbox messages."""
    while True:
        try:
            await publish_outbox_messages()
        except Exception as e:
            logger.error(f"Error in outbox publisher loop: {e}")
        await asyncio.sleep(1)  # Check every second


async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def start_consumer():
    """Start the consumer application."""
    await broker.start()
    logger.info("Consumer started, waiting for messages...")
    
    # Start background task for publishing outbox messages
    asyncio.create_task(publish_outbox_messages_loop())
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down consumer...")
        await broker.close()


if __name__ == "__main__":
    asyncio.run(start_consumer())
