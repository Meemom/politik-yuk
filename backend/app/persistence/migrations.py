from dataclasses import dataclass
from pathlib import Path

from app.persistence.connection import DatabaseConnection

MIGRATIONS_PATH = Path(__file__).parent / "migrations"
SEEDS_PATH = Path(__file__).parent / "seeds"


@dataclass(frozen=True)
class Migration:
    migration_id: str
    sql: str


def load_migrations(path: Path = MIGRATIONS_PATH) -> list[Migration]:
    migrations = [
        Migration(migration_id=file_path.stem, sql=file_path.read_text(encoding="utf-8"))
        for file_path in sorted(path.glob("*.sql"))
    ]
    if not migrations:
        raise ValueError(f"No migrations found in {path}.")
    return migrations


def load_seed_sql(path: Path = SEEDS_PATH) -> str:
    seed_files = sorted(path.glob("*.sql"))
    if not seed_files:
        raise ValueError(f"No seed files found in {path}.")
    return "\n\n".join(file_path.read_text(encoding="utf-8") for file_path in seed_files)


def split_sql_statements(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def apply_migrations(connection: DatabaseConnection) -> list[str]:
    applied: list[str] = []
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_id text PRIMARY KEY,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        rows = cursor.execute("SELECT migration_id FROM schema_migrations").fetchall()
        existing = {str(row[0]) for row in rows}

        for migration in load_migrations():
            if migration.migration_id in existing:
                continue
            for statement in split_sql_statements(migration.sql):
                cursor.execute(statement)
            cursor.execute(
                "INSERT INTO schema_migrations (migration_id) VALUES (%s)",
                (migration.migration_id,),
            )
            applied.append(migration.migration_id)

    return applied
