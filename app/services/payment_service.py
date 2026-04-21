from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import json

from app.models import Payment, PaymentStatus, OutboxMessage


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, payment_id: str) -> Payment | None:
        result = await self.db.execute(select(Payment).where(Payment.id == payment_id))
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, idempotency_key: str) -> Payment | None:
        result = await self.db.execute(select(Payment).where(Payment.idempotency_key == idempotency_key))
        return result.scalar_one_or_none()

    async def create_payment(
        self, 
        request,  # CreatePaymentRequest - imported locally to avoid circular import
        idempotency_key: str
    ) -> Payment:
        import uuid
        from app.api.schemas import CreatePaymentRequest
        
        payment_id = str(uuid.uuid4())
        
        payment = Payment(
            id=payment_id,
            amount=request.amount,
            currency=request.currency.value,
            description=request.description,
            metadata_=request.metadata_,
            idempotency_key=idempotency_key,
            webhook_url=request.webhook_url,
            status=PaymentStatus.PENDING,
        )
        
        self.db.add(payment)
        
        # Create outbox message for guaranteed event publishing
        outbox_message = OutboxMessage(
            event_type="payment.created",
            payload={
                "payment_id": payment_id,
                "amount": str(request.amount),
                "currency": request.currency.value,
                "description": request.description,
                "metadata": request.metadata_,
                "webhook_url": request.webhook_url,
                "idempotency_key": idempotency_key,
            }
        )
        self.db.add(outbox_message)
        
        await self.db.commit()
        await self.db.refresh(payment)
        
        return payment

    async def update_payment_status(
        self, 
        payment_id: str, 
        status: PaymentStatus,
        processed_at: datetime | None = None
    ) -> Payment | None:
        payment = await self.get_by_id(payment_id)
        if not payment:
            return None
        
        payment.status = status
        payment.processed_at = processed_at or datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(payment)
        
        return payment

    async def create_outbox_message(self, event_type: str, payload: dict) -> OutboxMessage:
        outbox_message = OutboxMessage(
            event_type=event_type,
            payload=payload,
        )
        self.db.add(outbox_message)
        await self.db.commit()
        await self.db.refresh(outbox_message)
        return outbox_message

    async def mark_outbox_published(self, outbox_id: int) -> None:
        from sqlalchemy import update
        await self.db.execute(
            update(OutboxMessage)
            .where(OutboxMessage.id == outbox_id)
            .values(published=True, published_at=datetime.utcnow())
        )
        await self.db.commit()

    async def get_unpublished_outbox_messages(self, limit: int = 100) -> list[OutboxMessage]:
        result = await self.db.execute(
            select(OutboxMessage)
            .where(OutboxMessage.published == False)
            .order_by(OutboxMessage.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())
