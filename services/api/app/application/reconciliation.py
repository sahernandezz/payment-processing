from datetime import UTC, datetime, timedelta

from payment_db_models.enums import PaymentStatus
from payment_db_models.models import PaymentStatusHistory

from app.infrastructure.metrics import (
    reconciliation_processed,
    status_transitions,
    track_usecase,
)
from app.infrastructure.unit_of_work import UnitOfWork

RECONCILIATION_ACTOR = "service:reconciliation"


class ReconciliationService:
    def __init__(self, uow: UnitOfWork, timeout_minutes: int):
        self.uow = uow
        self.timeout_minutes = timeout_minutes

    def run(self) -> int:
        with track_usecase("reconcile_pending_payments"):
            cutoff = datetime.now(UTC) - timedelta(minutes=self.timeout_minutes)
            pending = self.uow.payments.pending_older_than(cutoff)
            for payment in pending:
                previous = payment.status
                payment.status = PaymentStatus.REJECTED
                self.uow.payments.add_history(
                    PaymentStatusHistory(
                        payment_id=payment.id,
                        previous_status=previous,
                        new_status=PaymentStatus.REJECTED,
                        reason="Auto-rejected: pending longer than allowed window",
                        changed_by=RECONCILIATION_ACTOR,
                    )
                )
                status_transitions.labels(
                    from_status=previous, to_status=PaymentStatus.REJECTED
                ).inc()
            self.uow.commit()
            reconciliation_processed.inc(len(pending))
            return len(pending)
