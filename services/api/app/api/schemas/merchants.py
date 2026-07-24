import uuid
from datetime import datetime
from decimal import Decimal

from payment_db_models.enums import MerchantStatus
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer


class MerchantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    document_number: str = Field(min_length=1, max_length=50)
    email: EmailStr


class MerchantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    document_number: str
    email: str
    status: MerchantStatus
    created_at: datetime
    updated_at: datetime


class MerchantSummary(BaseModel):
    merchant_id: uuid.UUID
    total_payments: int
    approved_payments: int
    rejected_payments: int
    pending_payments: int
    approved_amount: Decimal

    @field_serializer("approved_amount")
    def _amount(self, value: Decimal) -> int | float:
        return int(value) if value == value.to_integral_value() else float(value)
