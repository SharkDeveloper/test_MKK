"""
Tests for payment API endpoints.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Payment, PaymentStatus


class TestCreatePayment:
    """Tests for POST /api/v1/payments endpoint."""

    async def test_create_payment_success(
        self,
        client: AsyncClient,
        sample_payment_data: dict,
        sample_idempotency_key: str,
        api_key: str,
    ):
        """Test successful payment creation."""
        headers = {
            "X-API-Key": api_key,
            "Idempotency-Key": sample_idempotency_key,
        }

        response = await client.post("/api/v1/payments", json=sample_payment_data, headers=headers)

        assert response.status_code == 202
        data = response.json()
        
        assert "id" in data
        assert data["amount"] == "100.00"
        assert data["currency"] == "RUB"
        assert data["description"] == "Test payment"
        assert data["status"] == "pending"
        assert data["idempotency_key"] == sample_idempotency_key
        assert "created_at" in data

    async def test_create_payment_idempotency(
        self,
        client: AsyncClient,
        sample_payment_data: dict,
        sample_idempotency_key: str,
        api_key: str,
    ):
        """Test that duplicate requests with same idempotency key return same payment."""
        headers = {
            "X-API-Key": api_key,
            "Idempotency-Key": sample_idempotency_key,
        }

        # First request
        response1 = await client.post("/api/v1/payments", json=sample_payment_data, headers=headers)
        assert response1.status_code == 202
        payment1 = response1.json()

        # Second request with same idempotency key
        response2 = await client.post("/api/v1/payments", json=sample_payment_data, headers=headers)
        assert response2.status_code == 202
        payment2 = response2.json()

        # Should return the same payment
        assert payment1["id"] == payment2["id"]
        assert payment1["idempotency_key"] == payment2["idempotency_key"]

    async def test_create_payment_missing_idempotency_key(
        self,
        client: AsyncClient,
        sample_payment_data: dict,
        api_key: str,
    ):
        """Test that missing idempotency key returns 422 error."""
        headers = {"X-API-Key": api_key}

        response = await client.post("/api/v1/payments", json=sample_payment_data, headers=headers)

        assert response.status_code == 422

    async def test_create_payment_missing_api_key(
        self,
        client: AsyncClient,
        sample_payment_data: dict,
        sample_idempotency_key: str,
    ):
        """Test that missing API key returns 401 error."""
        headers = {"Idempotency-Key": sample_idempotency_key}

        response = await client.post("/api/v1/payments", json=sample_payment_data, headers=headers)

        assert response.status_code == 401

    async def test_create_payment_invalid_api_key(
        self,
        client: AsyncClient,
        sample_payment_data: dict,
        sample_idempotency_key: str,
    ):
        """Test that invalid API key returns 401 error."""
        headers = {
            "X-API-Key": "invalid-key",
            "Idempotency-Key": sample_idempotency_key,
        }

        response = await client.post("/api/v1/payments", json=sample_payment_data, headers=headers)

        assert response.status_code == 401

    async def test_create_payment_invalid_amount(
        self,
        client: AsyncClient,
        sample_idempotency_key: str,
        api_key: str,
    ):
        """Test that invalid amount (negative or zero) returns 422 error."""
        headers = {
            "X-API-Key": api_key,
            "Idempotency-Key": sample_idempotency_key,
        }

        invalid_data = {
            "amount": "-10.00",
            "currency": "RUB",
            "description": "Invalid payment",
        }

        response = await client.post("/api/v1/payments", json=invalid_data, headers=headers)

        assert response.status_code == 422

    async def test_create_payment_invalid_currency(
        self,
        client: AsyncClient,
        sample_idempotency_key: str,
        api_key: str,
    ):
        """Test that invalid currency returns 422 error."""
        headers = {
            "X-API-Key": api_key,
            "Idempotency-Key": sample_idempotency_key,
        }

        invalid_data = {
            "amount": "100.00",
            "currency": "INVALID",
            "description": "Invalid currency payment",
        }

        response = await client.post("/api/v1/payments", json=invalid_data, headers=headers)

        assert response.status_code == 422

    async def test_create_payment_without_metadata(
        self,
        client: AsyncClient,
        sample_idempotency_key: str,
        api_key: str,
    ):
        """Test payment creation without metadata."""
        headers = {
            "X-API-Key": api_key,
            "Idempotency-Key": sample_idempotency_key,
        }

        data = {
            "amount": "50.00",
            "currency": "USD",
            "description": "Payment without metadata",
        }

        response = await client.post("/api/v1/payments", json=data, headers=headers)

        assert response.status_code == 202
        payment = response.json()
        assert payment["metadata"] is None


class TestGetPayment:
    """Tests for GET /api/v1/payments/{payment_id} endpoint."""

    async def test_get_payment_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        sample_idempotency_key: str,
        api_key: str,
    ):
        """Test successful payment retrieval."""
        # Create a payment first
        from decimal import Decimal
        payment = Payment(
            id="test-payment-id-123",
            amount=Decimal("100.00"),
            currency="EUR",
            description="Test payment for retrieval",
            idempotency_key=sample_idempotency_key,
            status=PaymentStatus.PENDING,
        )
        db_session.add(payment)
        await db_session.commit()

        headers = {"X-API-Key": api_key}
        response = await client.get("/api/v1/payments/test-payment-id-123", headers=headers)

        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == "test-payment-id-123"
        assert data["currency"] == "EUR"
        assert data["status"] == "pending"

    async def test_get_payment_not_found(
        self,
        client: AsyncClient,
        api_key: str,
    ):
        """Test getting non-existent payment returns 404."""
        headers = {"X-API-Key": api_key}

        response = await client.get("/api/v1/payments/non-existent-id", headers=headers)

        assert response.status_code == 404

    async def test_get_payment_missing_api_key(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        sample_idempotency_key: str,
    ):
        """Test that missing API key returns 401 error."""
        # Create a payment first
        payment = Payment(
            id="test-payment-id-456",
            amount=100.00,
            currency="RUB",
            description="Test payment",
            idempotency_key=sample_idempotency_key,
            status=PaymentStatus.PENDING,
        )
        db_session.add(payment)
        await db_session.commit()

        response = await client.get("/api/v1/payments/test-payment-id-456")

        assert response.status_code == 401


class TestHealthCheck:
    """Tests for health check endpoint."""

    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")
        
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
