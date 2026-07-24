import uuid
from datetime import datetime

from payment_db_models.enums import PaymentMethod, PaymentStatus
from payment_db_models.models import Payment, PaymentStatusHistory
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


class PaymentRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, payment: Payment) -> Payment:
        self.session.add(payment)
        return payment

    def add_history(self, entry: PaymentStatusHistory) -> None:
        self.session.add(entry)

    def get(self, payment_id: uuid.UUID) -> Payment | None:
        return self.session.get(Payment, payment_id)

    def by_idempotency_key(self, key: str) -> Payment | None:
        return self.session.scalar(select(Payment).where(Payment.idempotency_key == key))

    def history(self, payment_id: uuid.UUID) -> list[PaymentStatusHistory]:
        stmt = (
            select(PaymentStatusHistory)
            .where(PaymentStatusHistory.payment_id == payment_id)
            .order_by(PaymentStatusHistory.created_at)
        )
        return list(self.session.scalars(stmt))

    def pending_older_than(self, cutoff: datetime) -> list[Payment]:
        # FOR UPDATE SKIP LOCKED: concurrent reconciliation runs (multiple workers or
        # duplicated beat instances) each take a disjoint set of rows, so every stale
        # payment is processed exactly once and no duplicate history is written.
        stmt = (
            select(Payment)
            .where(Payment.status == PaymentStatus.PENDING, Payment.created_at < cutoff)
            .with_for_update(skip_locked=True)
        )
        return list(self.session.scalars(stmt))

    def list(
        self,
        *,
        merchant_id: uuid.UUID | None = None,
        status: PaymentStatus | None = None,
        payment_method: PaymentMethod | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Payment], int]:
        stmt = select(Payment)
        stmt = self._apply_filters(
            stmt, merchant_id, status, payment_method, date_from, date_to
        )
        total = self.session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        stmt = stmt.order_by(Payment.created_at.desc()).offset((page - 1) * limit).limit(limit)
        return list(self.session.scalars(stmt)), int(total or 0)

    @staticmethod
    def _apply_filters(
        stmt: "Select[tuple[Payment]]",
        merchant_id: uuid.UUID | None,
        status: PaymentStatus | None,
        payment_method: PaymentMethod | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> "Select[tuple[Payment]]":
        if merchant_id is not None:
            stmt = stmt.where(Payment.merchant_id == merchant_id)
        if status is not None:
            stmt = stmt.where(Payment.status == status)
        if payment_method is not None:
            stmt = stmt.where(Payment.payment_method == payment_method)
        if date_from is not None:
            stmt = stmt.where(Payment.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Payment.created_at <= date_to)
        return stmt

    def summary(self, merchant_id: uuid.UUID) -> dict[str, object]:
        rows = self.session.execute(
            select(Payment.status, func.count(), func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.merchant_id == merchant_id)
            .group_by(Payment.status)
        ).all()
        by_status = {row[0]: (row[1], row[2]) for row in rows}
        total = sum(count for count, _ in by_status.values())
        approved_count, approved_amount = by_status.get(PaymentStatus.APPROVED, (0, 0))
        return {
            "total_payments": total,
            "approved_payments": approved_count,
            "rejected_payments": by_status.get(PaymentStatus.REJECTED, (0, 0))[0],
            "pending_payments": by_status.get(PaymentStatus.PENDING, (0, 0))[0],
            "approved_amount": approved_amount,
        }
