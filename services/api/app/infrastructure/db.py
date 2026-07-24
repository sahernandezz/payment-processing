from collections.abc import Iterator

from payment_db_models import make_engine, make_session_factory
from sqlalchemy.orm import Session

from app.config import get_settings

_engine = make_engine(get_settings().database_url)
SessionFactory = make_session_factory(_engine)


def get_session() -> Iterator[Session]:
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
