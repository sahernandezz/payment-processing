import json
import uuid
from typing import cast

import redis

from app.config import get_settings
from app.domain.errors import SessionExpired
from app.infrastructure.security.hashing import hash_token
from app.infrastructure.security.tokens import (
    decode_token,
    issue_access_token,
    issue_refresh_token,
)

_client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _key(user_id: str) -> str:
    return f"session:{user_id}"


class TokenPair:
    def __init__(self, access_token: str, refresh_token: str):
        self.access_token = access_token
        self.refresh_token = refresh_token


def start_session(user_id: str) -> TokenPair:
    """Create a single active session for the user, replacing any previous one."""
    return _issue(user_id, uuid.uuid4().hex)


def validate_access(token: str) -> str:
    payload = decode_token(token, "access")
    user_id, sid = payload["sub"], payload["sid"]
    stored = cast(str | None, _client.get(_key(user_id)))
    if not stored or json.loads(stored)["sid"] != sid:
        raise SessionExpired("Session is no longer active")
    return user_id


def refresh_session(refresh_token: str) -> TokenPair:
    payload = decode_token(refresh_token, "refresh")
    user_id, sid = payload["sub"], payload["sid"]
    stored = cast(str | None, _client.get(_key(user_id)))
    if not stored:
        raise SessionExpired("Session is no longer active")

    session = json.loads(stored)
    if session["refresh_hash"] != hash_token(refresh_token):
        # A valid-but-superseded refresh token was replayed: assume theft, kill session.
        _client.delete(_key(user_id))
        raise SessionExpired("Refresh token reuse detected")
    if session["sid"] != sid:
        raise SessionExpired("Session is no longer active")

    return _issue(user_id, uuid.uuid4().hex)


def end_session(user_id: str) -> None:
    _client.delete(_key(user_id))


def _issue(user_id: str, sid: str) -> TokenPair:
    access = issue_access_token(user_id, sid)
    refresh = issue_refresh_token(user_id, sid)
    value = json.dumps({"sid": sid, "refresh_hash": hash_token(refresh)})
    _client.set(_key(user_id), value, ex=get_settings().refresh_token_ttl_seconds)
    return TokenPair(access, refresh)
