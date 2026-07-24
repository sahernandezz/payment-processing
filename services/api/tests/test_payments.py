from fastapi.testclient import TestClient


def _payment_body(merchant_id: str, **overrides) -> dict:
    body = {
        "merchant_id": merchant_id,
        "external_reference": "ORDER-1",
        "amount": 150000,
        "currency": "COP",
        "payment_method": "QR",
    }
    body.update(overrides)
    return body


def _create(client, headers, merchant_id, key="key-1", **overrides):
    return client.post(
        "/api/v1/payments",
        headers={"Idempotency-Key": key, **headers},
        json=_payment_body(merchant_id, **overrides),
    )


def test_create_payment_ok(client: TestClient, admin_headers, merchant_id):
    resp = _create(client, admin_headers, merchant_id)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["amount"] == 150000
    assert data["currency"] == "COP"


def test_reject_invalid_amount(client: TestClient, admin_headers, merchant_id):
    resp = _create(client, admin_headers, merchant_id, amount=0)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_reject_unknown_merchant(client: TestClient, admin_headers):
    resp = _create(client, admin_headers, "00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "MERCHANT_NOT_FOUND"


def test_idempotent_replay_returns_same_payment(client: TestClient, admin_headers, merchant_id):
    first = _create(client, admin_headers, merchant_id, key="same-key")
    second = _create(client, admin_headers, merchant_id, key="same-key")
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


def test_duplicate_external_reference_conflicts(client: TestClient, admin_headers, merchant_id):
    _create(client, admin_headers, merchant_id, key="k1", external_reference="DUP")
    resp = _create(client, admin_headers, merchant_id, key="k2", external_reference="DUP")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DUPLICATE_EXTERNAL_REFERENCE"


def test_valid_status_transition(client: TestClient, admin_headers, merchant_id):
    payment_id = _create(client, admin_headers, merchant_id).json()["id"]
    resp = client.patch(
        f"/api/v1/payments/{payment_id}/status",
        headers=admin_headers,
        json={"status": "APPROVED", "reason": "confirmed"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"


def test_invalid_status_transition(client: TestClient, admin_headers, merchant_id):
    payment_id = _create(client, admin_headers, merchant_id).json()["id"]
    client.patch(
        f"/api/v1/payments/{payment_id}/status",
        headers=admin_headers,
        json={"status": "APPROVED"},
    )
    resp = client.patch(
        f"/api/v1/payments/{payment_id}/status",
        headers=admin_headers,
        json={"status": "REJECTED"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_PAYMENT_STATUS"


def test_history_tracks_changes(client: TestClient, admin_headers, merchant_id):
    payment_id = _create(client, admin_headers, merchant_id).json()["id"]
    client.patch(
        f"/api/v1/payments/{payment_id}/status",
        headers=admin_headers,
        json={"status": "CANCELLED", "reason": "customer"},
    )
    history = client.get(
        f"/api/v1/payments/{payment_id}/history", headers=admin_headers
    ).json()
    assert [h["new_status"] for h in history] == ["PENDING", "CANCELLED"]
    assert history[-1]["changed_by"].startswith("user:")


def test_list_filters_by_status(client: TestClient, admin_headers, merchant_id):
    _create(client, admin_headers, merchant_id, key="a", external_reference="A")
    approved_id = _create(
        client, admin_headers, merchant_id, key="b", external_reference="B"
    ).json()["id"]
    client.patch(
        f"/api/v1/payments/{approved_id}/status",
        headers=admin_headers,
        json={"status": "APPROVED"},
    )
    resp = client.get("/api/v1/payments?status=APPROVED", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == approved_id
