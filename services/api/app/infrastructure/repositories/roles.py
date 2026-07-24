from payment_db_models.models import Role
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload


class RoleRepository:
    def __init__(self, session: Session):
        self.session = session

    def by_name(self, name: str) -> Role | None:
        stmt = (
            select(Role)
            .where(Role.name == name)
            .options(selectinload(Role.permissions))
        )
        return self.session.scalar(stmt)
