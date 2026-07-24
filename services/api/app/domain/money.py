from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.domain.errors import InvalidAmount

CENTS = Decimal("0.01")


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "COP"

    @classmethod
    def create(cls, amount: Decimal | int | str, currency: str = "COP") -> "Money":
        try:
            value = Decimal(amount).quantize(CENTS)
        except (InvalidOperation, TypeError) as exc:
            raise InvalidAmount("Amount is not a valid number") from exc
        if value <= 0:
            raise InvalidAmount("Amount must be greater than zero")
        return cls(value, currency)
