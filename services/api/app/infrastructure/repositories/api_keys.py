from payment_db_models.enums import ApiKeyStatus
from payment_db_models.models import ApiKey
from sqlalchemy import select
from sqlalchemy.orm import Session


class ApiKeyRepository:
    def __init__(self, session: Session):
        self.session = session

    def by_hash(self, hashed_key: str) -> ApiKey | None:
        stmt = select(ApiKey).where(
            ApiKey.hashed_key == hashed_key, ApiKey.status == ApiKeyStatus.ACTIVE
        )
        return self.session.scalar(stmt)
