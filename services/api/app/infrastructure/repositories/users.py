import uuid

from payment_db_models.models import User
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, user: User) -> User:
        self.session.add(user)
        return user

    def by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .where(User.email == email)
            .options(selectinload(User.roles))
        )
        return self.session.scalar(stmt)

    def get(self, user_id: uuid.UUID) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles))
        )
        return self.session.scalar(stmt)
