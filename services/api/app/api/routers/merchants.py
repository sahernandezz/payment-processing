import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import Actor, get_merchant_service, require_permission
from app.api.schemas.merchants import MerchantCreate, MerchantOut, MerchantSummary
from app.application.merchants import MerchantService

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.post("", response_model=MerchantOut, status_code=status.HTTP_201_CREATED)
def create_merchant(
    payload: MerchantCreate,
    service: MerchantService = Depends(get_merchant_service),
    _: Actor = Depends(require_permission("merchants:create")),
) -> MerchantOut:
    merchant = service.create(
        name=payload.name,
        document_number=payload.document_number,
        email=payload.email,
    )
    return MerchantOut.model_validate(merchant)


@router.get("/{merchant_id}", response_model=MerchantOut)
def get_merchant(
    merchant_id: uuid.UUID,
    service: MerchantService = Depends(get_merchant_service),
    _: Actor = Depends(require_permission("merchants:read")),
) -> MerchantOut:
    return MerchantOut.model_validate(service.get(merchant_id))


@router.get("/{merchant_id}/summary", response_model=MerchantSummary)
def merchant_summary(
    merchant_id: uuid.UUID,
    service: MerchantService = Depends(get_merchant_service),
    _: Actor = Depends(require_permission("merchants:read")),
) -> MerchantSummary:
    return MerchantSummary.model_validate(service.summary(merchant_id))
