from app.application.demo import DemoService
from app.application.reconciliation import ReconciliationService
from app.infrastructure.db import SessionFactory
from app.infrastructure.unit_of_work import UnitOfWork
from payment_db_models.enums import PaymentStatus
from payment_db_models.models import Merchant, Payment


def _merchant() -> None:
    with SessionFactory() as session:
        session.add(Merchant(name="D", document_number="D-1", email="d@example.com"))
        session.commit()


def test_random_payments_are_picked_up_by_reconciliation():
    _merchant()
    with SessionFactory() as session:
        created = DemoService(UnitOfWork(session)).create_random_payments(3, age_minutes=45)
        ids = [p.id for p in created]

    assert len(ids) == 3

    with SessionFactory() as session:
        assert ReconciliationService(UnitOfWork(session), timeout_minutes=30).run() == 3

    with SessionFactory() as session:
        assert all(session.get(Payment, i).status == PaymentStatus.REJECTED for i in ids)


def test_fresh_random_payments_are_left_alone():
    _merchant()
    with SessionFactory() as session:
        created = DemoService(UnitOfWork(session)).create_random_payments(2, age_minutes=0)
        ids = [p.id for p in created]

    with SessionFactory() as session:
        assert ReconciliationService(UnitOfWork(session), timeout_minutes=30).run() == 0

    with SessionFactory() as session:
        assert all(session.get(Payment, i).status == PaymentStatus.PENDING for i in ids)
