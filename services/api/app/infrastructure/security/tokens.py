from datetime import UTC, datetime, timedelta
from typing import cast

from jose import JWTError, jwt

from app.config import get_settings
from app.domain.errors import SessionExpired


def _encode(claims: dict[str, object], ttl_seconds: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {**claims, "iat": now, "exp": now + timedelta(seconds=ttl_seconds)}
    return cast(str, jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm))


def issue_access_token(user_id: str, sid: str) -> str:
    return _encode(
        {"sub": user_id, "sid": sid, "type": "access"},
        get_settings().access_token_ttl_seconds,
    )


def issue_refresh_token(user_id: str, sid: str) -> str:
    return _encode(
        {"sub": user_id, "sid": sid, "type": "refresh"},
        get_settings().refresh_token_ttl_seconds,
    )


def decode_token(token: str, expected_type: str) -> dict[str, str]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise SessionExpired("Invalid or expired token") from exc
    if payload.get("type") != expected_type:
        raise SessionExpired("Unexpected token type")
    return cast(dict[str, str], payload)
