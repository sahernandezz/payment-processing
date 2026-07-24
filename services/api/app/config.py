from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://payments:change_me@localhost:5432/payment_processing"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change_me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 604800

    pending_timeout_minutes: int = 30

    # Advertised in the OpenAPI `servers` block so generated clients/Postman have a base URL.
    public_url: str = "http://localhost:8000"

    # Demo-only endpoints (data seeding). Off by default so they never reach production.
    demo_endpoints_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
