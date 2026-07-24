import time
from collections.abc import Iterator
from contextlib import contextmanager

from prometheus_client import Counter, Histogram

usecase_duration = Histogram(
    "payments_usecase_duration_seconds",
    "Duration of application use cases",
    ["operation"],
)

idempotency_conflicts = Counter(
    "payments_idempotency_conflicts_total",
    "Payment creation requests resolved via an idempotency/unique conflict",
)

status_transitions = Counter(
    "payments_status_transitions_total",
    "Payment status transitions applied",
    ["from_status", "to_status"],
)

reconciliation_processed = Counter(
    "payments_reconciliation_processed_total",
    "Payments auto-rejected by the reconciliation job",
)


@contextmanager
def track_usecase(operation: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        usecase_duration.labels(operation=operation).observe(time.perf_counter() - start)
