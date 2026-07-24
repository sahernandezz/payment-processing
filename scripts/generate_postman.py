"""Genera la colección de Postman del proyecto.

    python -m scripts.generate_postman

Escribe docs/postman/payment-processing.postman_collection.json.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "postman"

SAVE_TOKENS = """const b = pm.response.json();
pm.collectionVariables.set("accessToken", b.access_token);
pm.collectionVariables.set("refreshToken", b.refresh_token);
pm.test("status 200", () => pm.response.to.have.status(200));"""

SAVE_MERCHANT = """pm.collectionVariables.set("merchantId", pm.response.json().id);
pm.test("status 201", () => pm.response.to.have.status(201));"""

REPLAY_CHECK = """pm.test("status 201", () => pm.response.to.have.status(201));
pm.test("idempotent: same payment as the first call", () =>
  pm.expect(pm.response.json().id).to.eql(pm.collectionVariables.get("paymentId")));"""

# Fresh identifiers per run so the collection can be replayed against the same database.
NEW_RUN_ID = 'pm.collectionVariables.set("runId", Date.now());'
NEW_IDEMPOTENCY_KEY = 'pm.collectionVariables.set("idempotencyKey", "payment-" + Date.now());'

SAVE_PAYMENT = """pm.collectionVariables.set("paymentId", pm.response.json().id);
pm.test("status 201", () => pm.response.to.have.status(201));"""


def url(path: str, query: list[dict[str, str]] | None = None) -> dict[str, object]:
    raw = "{{baseUrl}}" + path
    parsed: dict[str, object] = {
        "raw": raw + ("?" + "&".join(f"{q['key']}={q['value']}" for q in query) if query else ""),
        "host": ["{{baseUrl}}"],
        "path": [p for p in path.split("/") if p],
    }
    if query:
        parsed["query"] = query
    return parsed


def request(
    name: str,
    method: str,
    path: str,
    *,
    body: dict | None = None,
    headers: list[dict[str, str]] | None = None,
    query: list[dict[str, str]] | None = None,
    script: str | None = None,
    prerequest: str | None = None,
    auth: dict | None = None,
) -> dict[str, object]:
    req: dict[str, object] = {"method": method, "header": headers or [], "url": url(path, query)}
    if body is not None:
        req["header"] = [{"key": "Content-Type", "value": "application/json"}, *(headers or [])]
        req["body"] = {"mode": "raw", "raw": json.dumps(body, indent=2)}
    if auth is not None:
        req["auth"] = auth
    item: dict[str, object] = {"name": name, "request": req}
    events = []
    if prerequest:
        events.append(
            {
                "listen": "prerequest",
                "script": {"type": "text/javascript", "exec": prerequest.splitlines()},
            }
        )
    if script:
        events.append(
            {"listen": "test", "script": {"type": "text/javascript", "exec": script.splitlines()}}
        )
    if events:
        item["event"] = events
    return item


def build() -> dict[str, object]:
    no_auth = {"type": "noauth"}
    api_key_auth = {
        "type": "apikey",
        "apikey": [
            {"key": "key", "value": "X-API-Key"},
            {"key": "value", "value": "{{serviceApiKey}}"},
            {"key": "in", "value": "header"},
        ],
    }

    auth_folder = {
        "name": "Auth",
        "item": [
            request(
                "Register user",
                "POST",
                "/api/v1/auth/register",
                body={"email": "operator@example.com", "password": "password123"},
                auth=no_auth,
            ),
            request(
                "Login (saves tokens)",
                "POST",
                "/api/v1/auth/login",
                body={"email": "{{adminEmail}}", "password": "{{adminPassword}}"},
                script=SAVE_TOKENS,
                auth=no_auth,
            ),
            request(
                "Refresh (rotates tokens)",
                "POST",
                "/api/v1/auth/refresh",
                body={"refresh_token": "{{refreshToken}}"},
                script=SAVE_TOKENS,
                auth=no_auth,
            ),
        ],
    }

    merchants_folder = {
        "name": "Merchants",
        "item": [
            request(
                "Create merchant (saves merchantId)",
                "POST",
                "/api/v1/merchants",
                body={
                    "name": "Comercio Prueba",
                    "document_number": "{{runId}}",
                    "email": "comercio{{runId}}@example.com",
                },
                prerequest=NEW_RUN_ID,
                script=SAVE_MERCHANT,
            ),
            request("Get merchant", "GET", "/api/v1/merchants/{{merchantId}}"),
            request("Merchant summary", "GET", "/api/v1/merchants/{{merchantId}}/summary"),
        ],
    }

    payment_body = {
        "merchant_id": "{{merchantId}}",
        "external_reference": "ORDER-{{runId}}",
        "amount": 150000,
        "currency": "COP",
        "payment_method": "QR",
    }
    idem_header = [{"key": "Idempotency-Key", "value": "{{idempotencyKey}}"}]

    payments_folder = {
        "name": "Payments",
        "item": [
            request(
                "Create payment (saves paymentId)",
                "POST",
                "/api/v1/payments",
                body=payment_body,
                headers=idem_header,
                prerequest=NEW_IDEMPOTENCY_KEY,
                script=SAVE_PAYMENT,
            ),
            request(
                "Create payment - idempotent replay (same key)",
                "POST",
                "/api/v1/payments",
                body=payment_body,
                headers=idem_header,
                script=REPLAY_CHECK,
            ),
            request(
                "List payments (filters + pagination)",
                "GET",
                "/api/v1/payments",
                query=[
                    {"key": "merchant_id", "value": "{{merchantId}}"},
                    {"key": "status", "value": "PENDING"},
                    {"key": "page", "value": "1"},
                    {"key": "limit", "value": "20"},
                ],
            ),
            request("Get payment", "GET", "/api/v1/payments/{{paymentId}}"),
            request(
                "Approve payment",
                "PATCH",
                "/api/v1/payments/{{paymentId}}/status",
                body={"status": "APPROVED", "reason": "Pago confirmado por la pasarela"},
            ),
            request("Payment history", "GET", "/api/v1/payments/{{paymentId}}/history"),
            request(
                "Get payment as service (API Key)",
                "GET",
                "/api/v1/payments/{{paymentId}}",
                auth=api_key_auth,
            ),
        ],
    }

    demo_folder = {
        "name": "Demo",
        "item": [
            request(
                "Generate stale random payments",
                "POST",
                "/api/v1/demo/payments/random",
                body={"count": 3, "age_minutes": 45},
            ),
        ],
    }

    return {
        "info": {
            "name": "Payment Processing API",
            "description": "Colección de la API de procesamiento de pagos. Ejecutar 'Login' "
            "primero: guarda el token automáticamente en las variables de la colección.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{accessToken}}"}]},
        "item": [
            auth_folder,
            merchants_folder,
            payments_folder,
            demo_folder,
            {"name": "Health", "item": [request("Health", "GET", "/health", auth=no_auth)]},
        ],
        "variable": [
            {"key": "baseUrl", "value": "http://localhost:8000"},
            {"key": "adminEmail", "value": "admin@payments.com"},
            {"key": "adminPassword", "value": "admin12345"},
            {"key": "serviceApiKey", "value": "local-service-key-change-me"},
            {"key": "idempotencyKey", "value": ""},
            {"key": "runId", "value": ""},
            {"key": "accessToken", "value": ""},
            {"key": "refreshToken", "value": ""},
            {"key": "merchantId", "value": ""},
            {"key": "paymentId", "value": ""},
        ],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "payment-processing.postman_collection.json"
    target.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
