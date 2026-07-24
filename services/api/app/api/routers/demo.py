from fastapi import APIRouter, Depends, status

from app.api.deps import Actor, get_uow, require_permission
from app.api.schemas.demo import DemoPaymentsRequest, DemoPaymentsResponse
from app.api.schemas.payments import PaymentOut
from app.application.demo import DemoService
from app.infrastructure.unit_of_work import UnitOfWork

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post(
    "/payments/random",
    response_model=DemoPaymentsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Genera pagos PENDING antiguos para probar la conciliación",
)
def create_random_payments(
    payload: DemoPaymentsRequest,
    uow: UnitOfWork = Depends(get_uow),
    _: Actor = Depends(require_permission("payments:create")),
) -> DemoPaymentsResponse:
    payments = DemoService(uow).create_random_payments(payload.count, payload.age_minutes)
    return DemoPaymentsResponse(
        created=len(payments),
        age_minutes=payload.age_minutes,
        payments=[PaymentOut.model_validate(p) for p in payments],
    )
