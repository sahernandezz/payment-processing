from sqlalchemy.orm import Session

from app.infrastructure.repositories.api_keys import ApiKeyRepository
from app.infrastructure.repositories.merchants import MerchantRepository
from app.infrastructure.repositories.payments import PaymentRepository
from app.infrastructure.repositories.roles import RoleRepository
from app.infrastructure.repositories.users import UserRepository


class UnitOfWork:
    def __init__(self, session: Session):
        self.session = session
        self.merchants = MerchantRepository(session)
        self.payments = PaymentRepository(session)
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)
        self.api_keys = ApiKeyRepository(session)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def flush(self) -> None:
        self.session.flush()
