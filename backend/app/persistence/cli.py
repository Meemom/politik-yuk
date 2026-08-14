import argparse

from app.persistence.connection import postgres_connection
from app.persistence.migrations import apply_migrations, load_seed_sql, split_sql_statements
from app.settings import get_settings


def migrate() -> None:
    settings = get_settings()
    with postgres_connection(settings) as connection:
        applied = apply_migrations(connection)
    if applied:
        print(f"Applied migrations: {', '.join(applied)}")
    else:
        print("No migrations to apply.")


def seed() -> None:
    settings = get_settings()
    seed_sql = load_seed_sql()
    with postgres_connection(settings) as connection, connection.cursor() as cursor:
        for statement in split_sql_statements(seed_sql):
            cursor.execute(statement)
    print("Applied local seed data.")


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
