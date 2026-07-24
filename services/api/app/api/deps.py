import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.auth import AuthService
from app.application.merchants import MerchantService
from app.application.payments import PaymentService
from app.domain.errors import AuthenticationRequired, PermissionDenied, SessionExpired
from app.infrastructure.db import get_session
from app.infrastructure.security.hashing import hash_token
from app.infrastructure.security.sessions import validate_access
from app.infrastructure.unit_of_work import UnitOfWork

SERVICE_PERMISSIONS = {
    "payments:create",
    "payments:read",
    "payments:transition",
    "merchants:read",
}

# auto_error=False so both schemes stay optional and we can fall back between them.
bearer_scheme = HTTPBearer(auto_error=False, scheme_name="userJWT")
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="serviceApiKey")


@dataclass
class Actor:
    label: str
    permissions: set[str]


def get_uow(session: Session = Depends(get_session)) -> Iterator[UnitOfWork]:
    yield UnitOfWork(session)


def get_payment_service(uow: UnitOfWork = Depends(get_uow)) -> PaymentService:
    return PaymentService(uow)


def get_merchant_service(uow: UnitOfWork = Depends(get_uow)) -> MerchantService:
    return MerchantService(uow)


def get_auth_service(uow: UnitOfWork = Depends(get_uow)) -> AuthService:
    return AuthService(uow)


def get_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Depends(api_key_scheme),
    uow: UnitOfWork = Depends(get_uow),
) -> Actor:
    if credentials is not None:
        user_id = validate_access(credentials.credentials)
        user = uow.users.get(uuid.UUID(user_id))
        if user is None or not user.is_active:
            raise SessionExpired("Session is no longer active")
        return Actor(f"user:{user.id}", user.permission_codes())

    if api_key:
        record = uow.api_keys.by_hash(hash_token(api_key))
        if record is not None:
            return Actor(f"service:{record.id}", set(SERVICE_PERMISSIONS))

    raise AuthenticationRequired("Authentication credentials were not provided")


def require_permission(code: str) -> Callable[[Actor], Actor]:
    def dependency(actor: Actor = Depends(get_actor)) -> Actor:
        if code not in actor.permissions:
            raise PermissionDenied(f"Missing required permission: {code}")
        return actor

    return dependency
