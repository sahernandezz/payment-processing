from pathlib import Path

from alembic import op

_SQL_DIR = Path(__file__).parent / "alembic" / "sql"


def run_sql_file(filename: str) -> None:
    """Execute a plain .sql file statement by statement within the migration."""
    raw = (_SQL_DIR / filename).read_text()
    without_comments = "\n".join(
        line for line in raw.splitlines() if not line.strip().startswith("--")
    )
    for statement in filter(str.strip, without_comments.split(";")):
        op.execute(statement.strip())
