"""Ejecuta la conciliación una sola vez y termina. Útil como cron del sistema o para demos.

    python -m worker.run_once
"""
from app.application.reconciliation import ReconciliationService
from app.config import get_settings
from app.infrastructure.db import SessionFactory
from app.infrastructure.unit_of_work import UnitOfWork


def main() -> int:
    session = SessionFactory()
    try:
        uow = UnitOfWork(session)
        count = ReconciliationService(uow, get_settings().pending_timeout_minutes).run()
        print(f"Reconciliation rejected {count} stale pending payments")
        return count
    finally:
        session.close()


if __name__ == "__main__":
    main()
