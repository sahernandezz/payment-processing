from app.application.reconciliation import ReconciliationService
from app.config import get_settings
from app.infrastructure.db import SessionFactory
from app.infrastructure.unit_of_work import UnitOfWork
from celery.utils.log import get_task_logger

from worker.celery_app import app

logger = get_task_logger(__name__)


@app.task(name="worker.tasks.reconcile_pending_payments")
def reconcile_pending_payments() -> int:
    session = SessionFactory()
    try:
        uow = UnitOfWork(session)
        count = ReconciliationService(uow, get_settings().pending_timeout_minutes).run()
        logger.info("Reconciliation rejected %s stale pending payments", count)
        return count
    finally:
        session.close()
