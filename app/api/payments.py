from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.api.schemas import CreatePaymentRequest, PaymentResponse
from app.db.session import get_db
from app.services.payment_service import PaymentService
from app.core.config import settings


router = APIRouter(prefix="/payments", tags=["payments"])


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_api_key)],
    summary="Create a new payment",
)
async def create_payment(
    request: CreatePaymentRequest,
    idempotency_key: str = Header(..., description="Unique key to prevent duplicate payments"),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new payment request. The payment will be processed asynchronously.
    
    - **idempotency_key**: Required header to prevent duplicate payments
    - **amount**: Payment amount (must be > 0)
    - **currency**: RUB, USD, or EUR
    - **description**: Payment description
    - **metadata**: Optional additional data
    - **webhook_url**: Optional URL for result notification
    """
    service = PaymentService(db)
    
    # Check for existing payment with same idempotency key
    existing = await service.get_by_idempotency_key(idempotency_key)
    if existing:
        return PaymentResponse.model_validate(existing)
    
    # Create new payment
    payment = await service.create_payment(request, idempotency_key)
    
    return PaymentResponse.model_validate(payment)


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    dependencies=[Depends(verify_api_key)],
    summary="Get payment details",
)
async def get_payment(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed information about a specific payment by its ID.
    """
    service = PaymentService(db)
    payment = await service.get_by_id(payment_id)
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with id {payment_id} not found",
        )
    
    return PaymentResponse.model_validate(payment)
