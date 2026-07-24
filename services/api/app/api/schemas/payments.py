import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from payment_db_models.enums import PaymentMethod, PaymentStatus
from pydantic import BaseModel, ConfigDict, Field, field_serializer


class PaymentCreate(BaseModel):
    merchant_id: uuid.UUID
    external_reference: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(gt=0)
    currency: Literal["COP"] = "COP"
    payment_method: PaymentMethod


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_id: uuid.UUID
    external_reference: str
    amount: Decimal
    currency: str
    payment_method: PaymentMethod
    status: PaymentStatus
    created_at: datetime
    updated_at: datetime

    @field_serializer("amount")
    def _amount(self, value: Decimal) -> int | float:
        return int(value) if value == value.to_integral_value() else float(value)


class PaymentStatusUpdate(BaseModel):
    status: PaymentStatus
    reason: str | None = Field(default=None, max_length=255)


class PaymentHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    previous_status: PaymentStatus | None
    new_status: PaymentStatus
    reason: str | None
    changed_by: str
    created_at: datetime


class PaymentPage(BaseModel):
    items: list[PaymentOut]
    page: int
    limit: int
    total: int
