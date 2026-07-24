from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from app.application.reconciliation import ReconciliationService
from app.infrastructure.db import SessionFactory
from app.infrastructure.unit_of_work import UnitOfWork
from payment_db_models.enums import PaymentMethod, PaymentStatus
from payment_db_models.models import Merchant, Payment, PaymentStatusHistory
from sqlalchemy import func, select


def _stale_payment(merchant_id, ref: str, key: str) -> Payment:
    return Payment(
        merchant_id=merchant_id,
        external_reference=ref,
        amount=1000,
        currency="COP",
        payment_method=PaymentMethod.CARD,
        status=PaymentStatus.PENDING,
        idempotency_key=key,
        created_at=datetime.now(UTC) - timedelta(minutes=45),
    )


def test_reconcile_rejects_stale_pending_payments():
    with SessionFactory() as session:
        merchant = Merchant(name="R", document_number="R-1", email="r@example.com")
        session.add(merchant)
        session.flush()

        stale = Payment(
            merchant_id=merchant.id,
            external_reference="STALE",
            amount=1000,
            currency="COP",
            payment_method=PaymentMethod.CARD,
            status=PaymentStatus.PENDING,
            idempotency_key="stale",
            created_at=datetime.now(UTC) - timedelta(minutes=45),
        )
        fresh = Payment(
            merchant_id=merchant.id,
            external_reference="FRESH",
            amount=1000,
            currency="COP",
            payment_method=PaymentMethod.CARD,
            status=PaymentStatus.PENDING,
            idempotency_key="fresh",
        )
        session.add_all([stale, fresh])
        session.commit()
        stale_id, fresh_id = stale.id, fresh.id

    with SessionFactory() as session:
        processed = ReconciliationService(UnitOfWork(session), timeout_minutes=30).run()
        assert processed == 1

    with SessionFactory() as session:
        assert session.get(Payment, stale_id).status == PaymentStatus.REJECTED
        assert session.get(Payment, fresh_id).status == PaymentStatus.PENDING


def test_concurrent_reconciliation_processes_each_payment_once():
    count = 20
    with SessionFactory() as session:
        merchant = Merchant(name="C", document_number="C-1", email="c@example.com")
        session.add(merchant)
        session.flush()
        session.add_all(
            [_stale_payment(merchant.id, f"REF-{i}", f"key-{i}") for i in range(count)]
        )
        session.commit()

    def run() -> int:
        with SessionFactory() as session:
            return ReconciliationService(UnitOfWork(session), timeout_minutes=30).run()

    with ThreadPoolExecutor(max_workers=4) as pool:
        totals = list(pool.map(lambda _: run(), range(4)))

    # Every stale payment is processed exactly once across all concurrent runs.
    assert sum(totals) == count

    with SessionFactory() as session:
        rejected = session.scalar(
            select(func.count())
            .select_from(Payment)
            .where(Payment.status == PaymentStatus.REJECTED)
        )
        history_rows = session.scalar(
            select(func.count())
            .select_from(PaymentStatusHistory)
            .where(PaymentStatusHistory.new_status == PaymentStatus.REJECTED)
        )
    assert rejected == count
    # No duplicate history: exactly one REJECTED entry per payment.
    assert history_rows == count
