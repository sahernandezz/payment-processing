import os

from celery import Celery
from celery.signals import worker_ready
from prometheus_client import start_http_server

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
interval = float(os.environ.get("RECONCILIATION_INTERVAL_SECONDS", "300"))
metrics_port = int(os.environ.get("METRICS_PORT", "9808"))

app = Celery("payment_reconciliation", broker=broker_url)
app.conf.timezone = "UTC"
app.conf.beat_schedule = {
    "reconcile-pending-payments": {
        "task": "worker.tasks.reconcile_pending_payments",
        "schedule": interval,
    }
}


@worker_ready.connect
def _start_metrics_server(**_: object) -> None:
    start_http_server(metrics_port)


import worker.tasks  # noqa: E402,F401  (registers the task)
