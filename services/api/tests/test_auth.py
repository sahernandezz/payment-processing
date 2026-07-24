from fastapi.testclient import TestClient


def test_protected_endpoint_requires_auth(client: TestClient):
    resp = client.get("/api/v1/payments")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_register_and_login(client: TestClient):
    client.post(
        "/api/v1/auth/register",
        json={"email": "user1@example.com", "password": "password123"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "user1@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_operator_cannot_create_merchant(client: TestClient):
    client.post(
        "/api/v1/auth/register",
        json={"email": "op@example.com", "password": "password123"},
    )
    tokens = client.post(
        "/api/v1/auth/login",
        json={"email": "op@example.com", "password": "password123"},
    ).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = client.post(
        "/api/v1/merchants",
        headers=headers,
        json={"name": "X", "document_number": "999", "email": "x@example.com"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "PERMISSION_DENIED"


def test_refresh_rotation_detects_reuse(client: TestClient):
    tokens = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@payments.com", "password": "admin12345"},
    ).json()
    old_refresh = tokens["refresh_token"]

    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert rotated.status_code == 200
    new_refresh = rotated.json()["refresh_token"]

    # Replaying the old (already rotated) token is treated as theft.
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "SESSION_EXPIRED"

    # The session was killed, so even the new token no longer works.
    after = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert after.status_code == 401


def test_wrong_password_rejected(client: TestClient):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@payments.com", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"
