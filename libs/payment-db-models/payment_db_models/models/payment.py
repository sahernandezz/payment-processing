import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from payment_db_models.base import Base, TimestampMixin, uuid_pk
from payment_db_models.enums import PaymentMethod, PaymentStatus


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("merchant_id", "external_reference", name="uq_merchant_external_ref"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id"), index=True)
    external_reference: Mapped[str] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="COP")
    payment_method: Mapped[PaymentMethod] = mapped_column(
        SAEnum(PaymentMethod, native_enum=False, length=20)
    )
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, native_enum=False, length=20),
        default=PaymentStatus.PENDING,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)

    merchant: Mapped["Merchant"] = relationship(back_populates="payments")
    history: Mapped[list["PaymentStatusHistory"]] = relationship(
        back_populates="payment", order_by="PaymentStatusHistory.created_at"
    )


class PaymentStatusHistory(Base):
    __tablename__ = "payment_status_history"

    id: Mapped[uuid.UUID] = uuid_pk()
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id"), index=True)
    previous_status: Mapped[PaymentStatus | None] = mapped_column(
        SAEnum(PaymentStatus, native_enum=False, length=20), nullable=True
    )
    new_status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, native_enum=False, length=20)
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    changed_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    payment: Mapped["Payment"] = relationship(back_populates="history")


from payment_db_models.models.merchant import Merchant  # noqa: E402
