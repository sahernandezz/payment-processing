from enum import StrEnum


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class PaymentMethod(StrEnum):
    CARD = "CARD"
    QR = "QR"
    NFC = "NFC"
    TRANSFER = "TRANSFER"


class MerchantStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ApiKeyStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
