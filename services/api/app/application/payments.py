import uuid
from datetime import datetime
from decimal import Decimal

from payment_db_models.enums import PaymentMethod, PaymentStatus
from payment_db_models.models import Payment, PaymentStatusHistory
from sqlalchemy.exc import IntegrityError

from app.domain.errors import DuplicateExternalReference, MerchantNotFound, PaymentNotFound
from app.domain.money import Money
from app.domain.payment_status import assert_transition
from app.infrastructure.metrics import (
    idempotency_conflicts,
    status_transitions,
    track_usecase,
)
from app.infrastructure.unit_of_work import UnitOfWork


class PaymentService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def create(
        self,
        *,
        merchant_id: uuid.UUID,
        external_reference: str,
        amount: Decimal,
        currency: str,
        payment_method: PaymentMethod,
        idempotency_key: str,
        actor: str,
    ) -> Payment:
        with track_usecase("create_payment"):
            existing = self.uow.payments.by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing

            if self.uow.merchants.get(merchant_id) is None:
                raise MerchantNotFound("Merchant not found")

            money = Money.create(amount, currency)
            payment = Payment(
                merchant_id=merchant_id,
                external_reference=external_reference,
                amount=money.amount,
                currency=money.currency,
                payment_method=payment_method,
                status=PaymentStatus.PENDING,
                idempotency_key=idempotency_key,
            )
            self.uow.payments.add(payment)
            self.uow.payments.add_history(
                PaymentStatusHistory(
                    payment=payment,
                    previous_status=None,
                    new_status=PaymentStatus.PENDING,
                    reason="Payment created",
                    changed_by=actor,
                )
            )
            try:
                self.uow.commit()
            except IntegrityError:
                self.uow.rollback()
                return self._resolve_conflict(idempotency_key)
            return payment

    def _resolve_conflict(self, idempotency_key: str) -> Payment:
        existing = self.uow.payments.by_idempotency_key(idempotency_key)
        if existing is not None:
            idempotency_conflicts.inc()
            return existing
        raise DuplicateExternalReference(
            "A payment with this external reference already exists for the merchant"
        )

    def get(self, payment_id: uuid.UUID) -> Payment:
        payment = self.uow.payments.get(payment_id)
        if payment is None:
            raise PaymentNotFound("Payment not found")
        return payment

    def transition(
        self, payment_id: uuid.UUID, new_status: PaymentStatus, reason: str | None, actor: str
    ) -> Payment:
        with track_usecase("transition_payment_status"):
            payment = self.get(payment_id)
            assert_transition(payment.status, new_status)
            previous = payment.status
            payment.status = new_status
            self.uow.payments.add_history(
                PaymentStatusHistory(
                    payment_id=payment.id,
                    previous_status=previous,
                    new_status=new_status,
                    reason=reason,
                    changed_by=actor,
                )
            )
            self.uow.commit()
            status_transitions.labels(from_status=previous, to_status=new_status).inc()
            return payment

    def history(self, payment_id: uuid.UUID) -> list[PaymentStatusHistory]:
        self.get(payment_id)
        return self.uow.payments.history(payment_id)

    def list(
        self,
        *,
        merchant_id: uuid.UUID | None,
        status: PaymentStatus | None,
        payment_method: PaymentMethod | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        limit: int,
    ) -> tuple[list[Payment], int]:
        return self.uow.payments.list(
            merchant_id=merchant_id,
            status=status,
            payment_method=payment_method,
            date_from=date_from,
            date_to=date_to,
            page=page,
            limit=limit,
        )
