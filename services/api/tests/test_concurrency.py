from concurrent.futures import ThreadPoolExecutor

from app.infrastructure.db import SessionFactory
from fastapi.testclient import TestClient
from payment_db_models.models import Payment
from sqlalchemy import func, select


def test_concurrent_same_idempotency_key_creates_one_payment(
    client: TestClient, admin_headers, merchant_id
):
    body = {
        "merchant_id": merchant_id,
        "external_reference": "RACE-1",
        "amount": 250000,
        "currency": "COP",
        "payment_method": "TRANSFER",
    }
    headers = {"Idempotency-Key": "race-key", **admin_headers}

    def send() -> dict:
        resp = client.post("/api/v1/payments", headers=headers, json=body)
        return {"status": resp.status_code, "id": resp.json().get("id")}

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: send(), range(8)))

    ids = {r["id"] for r in results}
    assert all(r["status"] == 201 for r in results)
    assert len(ids) == 1

    with SessionFactory() as session:
        count = session.scalar(
            select(func.count()).select_from(Payment).where(Payment.idempotency_key == "race-key")
        )
    assert count == 1
