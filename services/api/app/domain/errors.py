class DomainError(Exception):
    code = "DOMAIN_ERROR"
    status = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class InvalidAmount(DomainError):
    code = "INVALID_AMOUNT"
    status = 422


class InvalidPaymentStatusTransition(DomainError):
    code = "INVALID_PAYMENT_STATUS"
    status = 422


class MerchantNotFound(DomainError):
    code = "MERCHANT_NOT_FOUND"
    status = 404


class PaymentNotFound(DomainError):
    code = "PAYMENT_NOT_FOUND"
    status = 404


class DuplicateExternalReference(DomainError):
    code = "DUPLICATE_EXTERNAL_REFERENCE"
    status = 409


class DuplicateMerchant(DomainError):
    code = "DUPLICATE_MERCHANT"
    status = 409


class InvalidCredentials(DomainError):
    code = "INVALID_CREDENTIALS"
    status = 401


class EmailAlreadyRegistered(DomainError):
    code = "EMAIL_ALREADY_REGISTERED"
    status = 409


class SessionExpired(DomainError):
    code = "SESSION_EXPIRED"
    status = 401


class PermissionDenied(DomainError):
    code = "PERMISSION_DENIED"
    status = 403


class AuthenticationRequired(DomainError):
    code = "AUTHENTICATION_REQUIRED"
    status = 401


class NoMerchantsAvailable(DomainError):
    code = "NO_MERCHANTS_AVAILABLE"
    status = 409
