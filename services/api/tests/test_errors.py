from app.api.main import create_app
from fastapi.testclient import TestClient


def test_malformed_json_returns_400(client: TestClient, admin_headers):
    resp = client.post(
        "/api/v1/merchants",
        headers={"Content-Type": "application/json", **admin_headers},
        content=b"{esto no es json",
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MALFORMED_REQUEST"


def test_well_formed_but_invalid_returns_422(client: TestClient, admin_headers):
    resp = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={"name": "X", "document_number": "1", "email": "no-es-email"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unexpected_error_returns_500(admin_headers, monkeypatch):
    from app.application import merchants as module

    def boom(*_args, **_kwargs):
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr(module.MerchantService, "create", boom)
    # raise_server_exceptions=False deja que el handler responda, como en producción.
    with TestClient(create_app(), raise_server_exceptions=False) as unsafe_client:
        resp = unsafe_client.post(
            "/api/v1/merchants",
            headers=admin_headers,
            json={"name": "X", "document_number": "500-test", "email": "x@example.com"},
        )
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
