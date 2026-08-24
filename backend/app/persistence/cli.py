import argparse
import time
from collections.abc import Callable

from app.persistence.connection import postgres_connection
from app.persistence.migrations import apply_migrations, load_seed_sql, split_sql_statements
from app.settings import get_settings


def migrate() -> None:
    settings = get_settings()

    def run_migrations() -> list[str]:
        with postgres_connection(settings) as connection:
            return apply_migrations(connection)

    applied = _with_database_retry(
        run_migrations,
        attempts=settings.migration_database_connect_attempts,
        delay_seconds=settings.migration_database_connect_delay_seconds,
    )
    if applied:
        print(f"Applied migrations: {', '.join(applied)}")
    else:
        print("No migrations to apply.")


def seed() -> None:
    settings = get_settings()
    seed_sql = load_seed_sql()

    def run_seed() -> None:
        with postgres_connection(settings) as connection, connection.cursor() as cursor:
            for statement in split_sql_statements(seed_sql):
                cursor.execute(statement)

    _with_database_retry(
        run_seed,
        attempts=settings.migration_database_connect_attempts,
        delay_seconds=settings.migration_database_connect_delay_seconds,
    )
    print("Applied local seed data.")


def _with_database_retry[T](
    operation: Callable[[], T],
    *,
    attempts: int,
    delay_seconds: float,
) -> T:
    last_error: Exception | None = None
    total_attempts = max(attempts, 1)
    for attempt in range(1, total_attempts + 1):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt == total_attempts:
                break
            print(
                "Database command failed "
                f"(attempt {attempt}/{total_attempts}); retrying in {delay_seconds:g}s: {exc}"
            )
            time.sleep(max(delay_seconds, 0))
    if last_error is None:
        raise RuntimeError("Database command failed without an exception.")
    raise last_error


def main() -> None:
    parser = argparse.ArgumentParser(description="Politik Yuk persistence commands.")
    parser.add_argument("command", choices=["migrate", "seed"])
    args = parser.parse_args()

    if args.command == "migrate":
        migrate()
    elif args.command == "seed":
        seed()


if __name__ == "__main__":
    main()
