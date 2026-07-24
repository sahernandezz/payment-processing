from payment_db_models.models import User
from sqlalchemy.exc import IntegrityError

from app.domain.errors import EmailAlreadyRegistered, InvalidCredentials
from app.domain.permissions import DEFAULT_USER_ROLE
from app.infrastructure.metrics import track_usecase
from app.infrastructure.security.hashing import hash_password, verify_password
from app.infrastructure.security.sessions import TokenPair, start_session
from app.infrastructure.unit_of_work import UnitOfWork


class AuthService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def register(self, email: str, password: str) -> User:
        with track_usecase("register_user"):
            
            if self.uow.users.by_email(email) is not None:
                raise EmailAlreadyRegistered("Email is already registered")
            
            user = User(email=email, hashed_password=hash_password(password))
            default_role = self.uow.roles.by_name(DEFAULT_USER_ROLE)
            if default_role is not None:
                user.roles.append(default_role)
            self.uow.users.add(user)
            try:
                self.uow.commit()
            except IntegrityError as exc:
                self.uow.rollback()
                raise EmailAlreadyRegistered("Email is already registered") from exc
            return user

    def login(self, email: str, password: str) -> TokenPair:
        with track_usecase("login_user"):
            user = self.uow.users.by_email(email)
            if user is None or not user.is_active:
                raise InvalidCredentials("Invalid email or password")
            if not verify_password(password, user.hashed_password):
                raise InvalidCredentials("Invalid email or password")
            return start_session(str(user.id))
