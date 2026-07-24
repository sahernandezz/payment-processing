import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://payments:change_me@localhost:5432/payment_processing_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("ADMIN_EMAIL", "admin@payments.com")
os.environ.setdefault("ADMIN_PASSWORD", "admin12345")

import psycopg  # noqa: E402
import pytest  # noqa: E402
from app.api.main import create_app  # noqa: E402
from app.infrastructure.db import SessionFactory, _engine  # noqa: E402
from app.infrastructure.security.sessions import _client as redis_client  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from payment_db_models import Base  # noqa: E402
from sqlalchemy import make_url, text  # noqa: E402

from scripts.seed import run as seed  # noqa: E402

_TRANSACTIONAL_TABLES = ["payment_status_history", "payments", "merchants"]


def _ensure_database() -> None:
    url = make_url(os.environ["DATABASE_URL"])
    admin = url.set(database="postgres").set(drivername="postgresql")
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{url.database}"')


@pytest.fixture(scope="session", autouse=True)
def _schema():
    _ensure_database()
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)
    seed()
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture(autouse=True)
def _clean():
    with SessionFactory() as session:
        session.execute(
            text(f"TRUNCATE {', '.join(_TRANSACTIONAL_TABLES)} RESTART IDENTITY CASCADE")
        )
        session.commit()
    redis_client.flushdb()
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@payments.com", "password": "admin12345"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def merchant_id(client: TestClient, admin_headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={"name": "Test Co", "document_number": "900111", "email": "test@example.com"},
    )
    return resp.json()["id"]
