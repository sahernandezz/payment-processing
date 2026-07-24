import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from payment_db_models.base import Base, TimestampMixin, uuid_pk
from payment_db_models.enums import MerchantStatus


class Merchant(Base, TimestampMixin):
    __tablename__ = "merchants"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200))
    document_number: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255))
    status: Mapped[MerchantStatus] = mapped_column(
        SAEnum(MerchantStatus, native_enum=False, length=20),
        default=MerchantStatus.ACTIVE,
    )

    payments: Mapped[list["Payment"]] = relationship(back_populates="merchant")


from payment_db_models.models.payment import Payment  # noqa: E402
