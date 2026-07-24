from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.errors import register_error_handlers
from app.api.routers import auth, demo, health, merchants, payments
from app.config import get_settings

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Payment Processing API",
        version="0.1.0",
        description="API de procesamiento de pagos: comercios, pagos, historial y conciliación.",
        servers=[{"url": settings.public_url, "description": "Servidor local"}],
    )

    register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(merchants.router, prefix=API_PREFIX)
    app.include_router(payments.router, prefix=API_PREFIX)
    if settings.demo_endpoints_enabled:
        app.include_router(demo.router, prefix=API_PREFIX)

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    return app


app = create_app()
