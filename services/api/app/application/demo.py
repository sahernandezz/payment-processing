import random
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from payment_db_models.enums import PaymentMethod, PaymentStatus
from payment_db_models.models import Payment, PaymentStatusHistory

from app.domain.errors import NoMerchantsAvailable
from app.infrastructure.unit_of_work import UnitOfWork


class DemoService:
    """Seeds random payments for demoing the reconciliation job.

    Payments are backdated so the job picks them up without waiting for the
    real timeout window to elapse.
    """

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def create_random_payments(self, count: int, age_minutes: int) -> list[Payment]:
        created_at = datetime.now(UTC) - timedelta(minutes=age_minutes)
        return [self._create_one(created_at) for _ in range(count)]

    def _create_one(self, created_at: datetime) -> Payment:
        merchant = self.uow.merchants.random()
        if merchant is None:
            raise NoMerchantsAvailable("Create a merchant before generating demo payments")

        suffix = uuid.uuid4().hex[:10]
        payment = Payment(
            merchant_id=merchant.id,
            external_reference=f"DEMO-{suffix.upper()}",
            amount=Decimal(random.randrange(1_000, 5_000_001)),
            currency="COP",
            payment_method=random.choice(list(PaymentMethod)),
            status=PaymentStatus.PENDING,
            idempotency_key=f"demo-{suffix}",
            created_at=created_at,
            updated_at=created_at,
        )
        self.uow.payments.add(payment)
        self.uow.payments.add_history(
            PaymentStatusHistory(
                payment=payment,
                previous_status=None,
                new_status=PaymentStatus.PENDING,
                reason="Demo payment generated",
                changed_by="service:demo",
                created_at=created_at,
            )
        )
        self.uow.commit()
        return payment
