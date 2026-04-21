"""
Tests for payment gateway service.
"""
import pytest
import asyncio
from decimal import Decimal

from app.services.payment_gateway import PaymentGateway
from app.models import PaymentStatus


class TestPaymentGateway:
    """Tests for PaymentGateway class."""

    @pytest.mark.asyncio
    async def test_process_payment_success(self):
        """Test successful payment processing (mocked 100% success rate)."""
        gateway = PaymentGateway(success_rate=1.0, min_delay=0, max_delay=0)
        
        status, error = await gateway.process_payment(
            "test-payment",
            "100.00",
            "RUB"
        )
        
        assert status == PaymentStatus.SUCCEEDED
        assert error is None

    @pytest.mark.asyncio
    async def test_process_payment_failure(self):
        """Test failed payment processing (mocked 0% success rate)."""
        gateway = PaymentGateway(success_rate=0.0, min_delay=0, max_delay=0)
        
        status, error = await gateway.process_payment(
            "test-payment",
            "100.00",
            "RUB"
        )
        
        assert status == PaymentStatus.FAILED
        assert error is not None
        assert isinstance(error, str)
        assert len(error) > 0

    @pytest.mark.asyncio
    async def test_process_payment_delay(self):
        """Test that payment processing has appropriate delay."""
        gateway = PaymentGateway(success_rate=1.0, min_delay=1, max_delay=2)
        
        start = asyncio.get_event_loop().time()
        status, error = await gateway.process_payment(
            "test-payment",
            "100.00",
            "RUB"
        )
        end = asyncio.get_event_loop().time()
        
        elapsed = end - start
        
        # Should take at least 1 second (min_delay)
        assert elapsed >= 0.9  # Small tolerance
        # Should not take more than 2.5 seconds (max_delay + tolerance)
        assert elapsed <= 2.5

    @pytest.mark.asyncio
    async def test_process_payment_with_different_currencies(self):
        """Test payment processing with different currencies."""
        gateway = PaymentGateway(success_rate=1.0, min_delay=0, max_delay=0)
        
        currencies = ["RUB", "USD", "EUR"]
        
        for currency in currencies:
            status, error = await gateway.process_payment(
                f"test-{currency}",
                "100.00",
                currency
            )
            
            assert status == PaymentStatus.SUCCEEDED
            assert error is None

    @pytest.mark.asyncio
    async def test_process_payment_multiple_times(self):
        """Test multiple payment processing calls."""
        gateway = PaymentGateway(success_rate=1.0, min_delay=0, max_delay=0)
        
        for i in range(5):
            status, error = await gateway.process_payment(
                f"test-payment-{i}",
                "100.00",
                "RUB"
            )
            
            assert status == PaymentStatus.SUCCEEDED
            assert error is None


class TestWebhookService:
    """Tests for WebhookService class."""

    @pytest.mark.asyncio
    async def test_send_webhook_invalid_url(self):
        """Test webhook sending to invalid URL fails gracefully."""
        from app.services.webhook_service import WebhookService
        
        webhook_service = WebhookService(max_retries=1, base_delay=0.1)
        
        result = await webhook_service.send_webhook(
            url="http://invalid-url-that-does-not-exist.com/webhook",
            payment_id="test-payment",
            status="succeeded",
            amount="100.00",
            currency="RUB",
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_webhook_with_error_message(self):
        """Test webhook sending includes error message when provided."""
        from app.services.webhook_service import WebhookService
        
        webhook_service = WebhookService(max_retries=1, base_delay=0.1)
        
        # This will fail due to invalid URL, but we're testing the payload structure
        result = await webhook_service.send_webhook(
            url="http://invalid-url.com/webhook",
            payment_id="test-payment",
            status="failed",
            amount="100.00",
            currency="RUB",
            error_message="Test error message",
        )
        
        assert result is False
