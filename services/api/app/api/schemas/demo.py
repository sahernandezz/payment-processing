from pydantic import BaseModel, Field

from app.api.schemas.payments import PaymentOut


class DemoPaymentsRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=50)
    age_minutes: int = Field(
        default=45,
        ge=0,
        le=10_080,
        description="Antigüedad del pago. Debe superar PENDING_TIMEOUT_MINUTES "
        "para que la conciliación lo rechace.",
    )


class DemoPaymentsResponse(BaseModel):
    created: int
    age_minutes: int
    payments: list[PaymentOut]
