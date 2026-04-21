"""
Tests for payment service.
"""
import pytest
from decimal import Decimal
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Payment, PaymentStatus, OutboxMessage
from app.services.payment_service import PaymentService


class TestPaymentService:
    """Tests for PaymentService class."""

    async def test_get_by_id(self, db_session: AsyncSession):
        """Test getting payment by ID."""
        payment = Payment(
            id="test-payment-123",
            amount=Decimal("100.00"),
            currency="RUB",
            description="Test payment",
            idempotency_key="test-key-123",
            status=PaymentStatus.PENDING,
        )
        db_session.add(payment)
        await db_session.commit()

        service = PaymentService(db_session)
        result = await service.get_by_id("test-payment-123")

        assert result is not None
        assert result.id == "test-payment-123"
        assert result.amount == Decimal("100.00")

    async def test_get_by_id_not_found(self, db_session: AsyncSession):
        """Test getting non-existent payment by ID."""
        service = PaymentService(db_session)
        result = await service.get_by_id("non-existent-id")

        assert result is None

    async def test_get_by_idempotency_key(self, db_session: AsyncSession):
        """Test getting payment by idempotency key."""
        payment = Payment(
            id="test-payment-456",
            amount=Decimal("200.00"),
            currency="USD",
            description="Test payment 2",
            idempotency_key="unique-key-456",
            status=PaymentStatus.PENDING,
        )
        db_session.add(payment)
        await db_session.commit()

        service = PaymentService(db_session)
        result = await service.get_by_idempotency_key("unique-key-456")

        assert result is not None
        assert result.id == "test-payment-456"
        assert result.idempotency_key == "unique-key-456"

    async def test_get_by_idempotency_key_not_found(self, db_session: AsyncSession):
        """Test getting payment with non-existent idempotency key."""
        service = PaymentService(db_session)
        result = await service.get_by_idempotency_key("non-existent-key")

        assert result is None

    async def test_create_payment(self, db_session: AsyncSession):
        """Test creating a new payment."""
        from app.api.schemas import CreatePaymentRequest, Currency

        request = CreatePaymentRequest(
            amount=Decimal("150.00"),
            currency=Currency.RUB,
            description="New test payment",
            metadata={"order_id": "999"},
            webhook_url="https://example.com/webhook",
        )

        service = PaymentService(db_session)
        payment = await service.create_payment(request, "new-idempotency-key")

        assert payment is not None
        assert payment.amount == Decimal("150.00")
        assert payment.currency == "RUB"
        assert payment.status == PaymentStatus.PENDING
        assert payment.idempotency_key == "new-idempotency-key"

        # Verify outbox message was created
        result = await db_session.execute(select(OutboxMessage))
        outbox_messages = result.scalars().all()
        assert len(outbox_messages) == 1
        assert outbox_messages[0].event_type == "payment.created"
        assert outbox_messages[0].payload["payment_id"] == payment.id

    async def test_update_payment_status(self, db_session: AsyncSession):
        """Test updating payment status."""
        payment = Payment(
            id="test-payment-status",
            amount=Decimal("50.00"),
            currency="EUR",
            description="Status update test",
            idempotency_key="status-key",
            status=PaymentStatus.PENDING,
        )
        db_session.add(payment)
        await db_session.commit()

        service = PaymentService(db_session)
        updated = await service.update_payment_status(
            "test-payment-status",
            PaymentStatus.SUCCEEDED,
        )

        assert updated is not None
        assert updated.status == PaymentStatus.SUCCEEDED
        assert updated.processed_at is not None

    async def test_update_payment_status_not_found(self, db_session: AsyncSession):
        """Test updating non-existent payment status."""
        service = PaymentService(db_session)
        result = await service.update_payment_status(
            "non-existent",
            PaymentStatus.FAILED,
        )

        assert result is None

    async def test_create_outbox_message(self, db_session: AsyncSession):
        """Test creating an outbox message."""
        service = PaymentService(db_session)
        outbox = await service.create_outbox_message(
            event_type="payment.test",
            payload={"test": "data"},
        )

        assert outbox is not None
        assert outbox.event_type == "payment.test"
        assert outbox.payload == {"test": "data"}
        assert outbox.published is False

    async def test_mark_outbox_published(self, db_session: AsyncSession):
        """Test marking outbox message as published."""
        outbox = OutboxMessage(
            event_type="payment.test",
            payload={"test": "data"},
        )
        db_session.add(outbox)
        await db_session.commit()

        service = PaymentService(db_session)
        await service.mark_outbox_published(outbox.id)

        await db_session.refresh(outbox)
        assert outbox.published is True
        assert outbox.published_at is not None

    async def test_get_unpublished_outbox_messages(self, db_session: AsyncSession):
        """Test getting unpublished outbox messages."""
        # Create published message
        published = OutboxMessage(
            event_type="payment.published",
            payload={"test": "published"},
            published=True,
        )
        # Create unpublished message
        unpublished = OutboxMessage(
            event_type="payment.unpublished",
            payload={"test": "unpublished"},
            published=False,
        )
        db_session.add_all([published, unpublished])
        await db_session.commit()

        service = PaymentService(db_session)
        result = await service.get_unpublished_outbox_messages()

        assert len(result) == 1
        assert result[0].event_type == "payment.unpublished"


class TestPaymentModel:
    """Tests for Payment model."""

    async def test_payment_repr(self, db_session: AsyncSession):
        """Test Payment string representation."""
        payment = Payment(
            id="test-repr",
            amount=Decimal("100.00"),
            currency="RUB",
            description="Test",
            idempotency_key="repr-key",
            status=PaymentStatus.PENDING,
        )
        db_session.add(payment)
        await db_session.commit()

        repr_str = repr(payment)
        assert "test-repr" in repr_str
        assert "PaymentStatus.PENDING" in repr_str or "pending" in repr_str.lower()
        assert "100.00" in repr_str


class TestOutboxMessageModel:
    """Tests for OutboxMessage model."""

    async def test_outbox_message_repr(self, db_session: AsyncSession):
        """Test OutboxMessage string representation."""
        outbox = OutboxMessage(
            event_type="payment.test",
            payload={"key": "value"},
        )
        db_session.add(outbox)
        await db_session.commit()

        assert "payment.test" in repr(outbox)
