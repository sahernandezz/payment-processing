"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-23

Schema defined in plain SQL under alembic/sql/; this revision only applies it.
"""
from collections.abc import Sequence

from payment_db_models.migrations_util import run_sql_file

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_sql_file("0001_initial.up.sql")


def downgrade() -> None:
    run_sql_file("0001_initial.down.sql")
