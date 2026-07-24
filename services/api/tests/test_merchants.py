from fastapi.testclient import TestClient


def test_create_and_get_merchant(client: TestClient, admin_headers):
    created = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={"name": "Acme", "document_number": "111222", "email": "acme@example.com"},
    )
    assert created.status_code == 201
    merchant_id = created.json()["id"]
    fetched = client.get(f"/api/v1/merchants/{merchant_id}", headers=admin_headers)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Acme"


def test_reject_invalid_email(client: TestClient, admin_headers):
    resp = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={"name": "Bad", "document_number": "333", "email": "not-an-email"},
    )
    assert resp.status_code == 422


def test_merchant_summary(client: TestClient, admin_headers, merchant_id):
    def create(key, ref):
        return client.post(
            "/api/v1/payments",
            headers={"Idempotency-Key": key, **admin_headers},
            json={
                "merchant_id": merchant_id,
                "external_reference": ref,
                "amount": 100000,
                "currency": "COP",
                "payment_method": "CARD",
            },
        ).json()["id"]

    approved = create("s1", "S1")
    create("s2", "S2")
    client.patch(
        f"/api/v1/payments/{approved}/status",
        headers=admin_headers,
        json={"status": "APPROVED"},
    )

    summary = client.get(
        f"/api/v1/merchants/{merchant_id}/summary", headers=admin_headers
    ).json()
    assert summary["total_payments"] == 2
    assert summary["approved_payments"] == 1
    assert summary["pending_payments"] == 1
    assert summary["approved_amount"] == 100000
