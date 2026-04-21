"""
Tests for Alembic migrations.
"""
import pytest
from sqlalchemy import text


class TestMigrations:
    """Tests for database migrations."""

    async def test_payments_table_exists(self, db_session):
        """Test that payments table is created by migrations."""
        from app.db.session import Base
        
        # Check if the table exists
        result = await db_session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='payments'")
        )
        tables = result.fetchall()
        
        assert len(tables) > 0
        assert "payments" in [t[0] for t in tables]

    async def test_outbox_messages_table_exists(self, db_session):
        """Test that outbox_messages table is created by migrations."""
        result = await db_session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='outbox_messages'")
        )
        tables = result.fetchall()
        
        assert len(tables) > 0
        assert "outbox_messages" in [t[0] for t in tables]

    async def test_payments_table_columns(self, db_engine):
        """Test that payments table has all required columns."""
        from sqlalchemy import inspect
        
        async with db_engine.begin() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: [col["name"] for col in inspect(sync_conn).get_columns("payments")]
            )
        
        expected_columns = [
            "id",
            "amount",
            "currency",
            "description",
            "metadata",
            "status",
            "idempotency_key",
            "webhook_url",
            "created_at",
            "updated_at",
            "processed_at",
        ]
        
        for column in expected_columns:
            assert column in columns, f"Column {column} is missing from payments table"

    async def test_outbox_messages_table_columns(self, db_engine):
        """Test that outbox_messages table has all required columns."""
        from sqlalchemy import inspect
        
        async with db_engine.begin() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: [col["name"] for col in inspect(sync_conn).get_columns("outbox_messages")]
            )
        
        expected_columns = [
            "id",
            "event_type",
            "payload",
            "published",
            "created_at",
            "published_at",
        ]
        
        for column in expected_columns:
            assert column in columns, f"Column {column} is missing from outbox_messages table"

    async def test_payments_idempotency_key_unique(self, db_session):
        """Test that idempotency_key column has unique constraint."""
        # Try to insert two payments with the same idempotency key
        from app.models import Payment, PaymentStatus
        from decimal import Decimal
        
        payment1 = Payment(
            id="unique-test-1",
            amount=Decimal("100.00"),
            currency="RUB",
            description="Test 1",
            idempotency_key="same-key",
            status=PaymentStatus.PENDING,
        )
        
        payment2 = Payment(
            id="unique-test-2",
            amount=Decimal("200.00"),
            currency="USD",
            description="Test 2",
            idempotency_key="same-key",  # Same key as payment1
            status=PaymentStatus.PENDING,
        )
        
        db_session.add(payment1)
        await db_session.commit()
        
        db_session.add(payment2)
        
        # Should raise an integrity error due to unique constraint
        with pytest.raises(Exception):
            await db_session.commit()

    async def test_payment_status_enum_values(self, db_session):
        """Test that payment status enum values are correct."""
        from app.models import Payment, PaymentStatus
        from decimal import Decimal
        
        valid_statuses = ["pending", "succeeded", "failed"]
        
        for status_value in valid_statuses:
            payment = Payment(
                id=f"status-test-{status_value}",
                amount=Decimal("50.00"),
                currency="RUB",
                description=f"Test {status_value}",
                idempotency_key=f"status-key-{status_value}",
                status=status_value,
            )
            db_session.add(payment)
            await db_session.flush()
        
        # Verify all were created successfully
        result = await db_session.execute(
            text("SELECT COUNT(*) FROM payments WHERE id LIKE 'status-test-%'")
        )
        count = result.scalar()
        assert count == 3
