from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any, Literal
from decimal import Decimal
from datetime import datetime
from enum import Enum


class Currency(str, Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class PaymentStatusEnum(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CreatePaymentRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    currency: Currency = Field(..., description="Currency code")
    description: str = Field(..., min_length=1, max_length=500, description="Payment description")
    metadata_: Optional[dict[str, Any]] = Field(None, alias="metadata", description="Additional metadata")
    webhook_url: Optional[str] = Field(None, max_length=500, description="Webhook URL for notifications")

    class Config:
        populate_by_name = True


class PaymentResponse(BaseModel):
    id: str
    amount: Decimal
    currency: str
    description: Optional[str]
    metadata_: Optional[dict[str, Any]] = Field(None, alias="metadata")
    status: PaymentStatusEnum
    idempotency_key: str
    webhook_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        from_attributes = True


class PaymentDetailResponse(PaymentResponse):
    pass
