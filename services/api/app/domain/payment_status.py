from payment_db_models.enums import PaymentStatus

from app.domain.errors import InvalidPaymentStatusTransition

_ALLOWED: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.PENDING: {
        PaymentStatus.APPROVED,
        PaymentStatus.REJECTED,
        PaymentStatus.CANCELLED,
    },
    PaymentStatus.APPROVED: set(),
    PaymentStatus.REJECTED: set(),
    PaymentStatus.CANCELLED: set(),
}


def assert_transition(current: PaymentStatus, new: PaymentStatus) -> None:
    if new not in _ALLOWED[current]:
        raise InvalidPaymentStatusTransition(
            f"Cannot change payment status from {current} to {new}"
        )
