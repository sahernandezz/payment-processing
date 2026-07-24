import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, status
from payment_db_models.enums import PaymentMethod, PaymentStatus

from app.api.deps import Actor, get_payment_service, require_permission
from app.api.schemas.payments import (
    PaymentCreate,
    PaymentHistoryOut,
    PaymentOut,
    PaymentPage,
    PaymentStatusUpdate,
)
from app.application.payments import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1),
    service: PaymentService = Depends(get_payment_service),
    actor: Actor = Depends(require_permission("payments:create")),
) -> PaymentOut:
    payment = service.create(
        merchant_id=payload.merchant_id,
        external_reference=payload.external_reference,
        amount=payload.amount,
        currency=payload.currency,
        payment_method=payload.payment_method,
        idempotency_key=idempotency_key,
        actor=actor.label,
    )
    return PaymentOut.model_validate(payment)


@router.get("", response_model=PaymentPage)
def list_payments(
    service: PaymentService = Depends(get_payment_service),
    _: Actor = Depends(require_permission("payments:read")),
    merchant_id: uuid.UUID | None = None,
    status: PaymentStatus | None = None,
    payment_method: PaymentMethod | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaymentPage:
    items, total = service.list(
        merchant_id=merchant_id,
        status=status,
        payment_method=payment_method,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )
    return PaymentPage(
        items=[PaymentOut.model_validate(p) for p in items],
        page=page,
        limit=limit,
        total=total,
    )


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: uuid.UUID,
    service: PaymentService = Depends(get_payment_service),
    _: Actor = Depends(require_permission("payments:read")),
) -> PaymentOut:
    return PaymentOut.model_validate(service.get(payment_id))


@router.patch("/{payment_id}/status", response_model=PaymentOut)
def update_status(
    payment_id: uuid.UUID,
    payload: PaymentStatusUpdate,
    service: PaymentService = Depends(get_payment_service),
    actor: Actor = Depends(require_permission("payments:transition")),
) -> PaymentOut:
    payment = service.transition(payment_id, payload.status, payload.reason, actor.label)
    return PaymentOut.model_validate(payment)


@router.get("/{payment_id}/history", response_model=list[PaymentHistoryOut])
def payment_history(
    payment_id: uuid.UUID,
    service: PaymentService = Depends(get_payment_service),
    _: Actor = Depends(require_permission("payments:read")),
) -> list[PaymentHistoryOut]:
    return [PaymentHistoryOut.model_validate(h) for h in service.history(payment_id)]
