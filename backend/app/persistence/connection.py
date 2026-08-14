from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import import_module
from types import TracebackType
from typing import Any, Protocol, Self

from app.settings import Settings


class DatabaseCursor(Protocol):
    def execute(self, query: str, params: tuple[object, ...] = ()) -> Self:
        ...

    def fetchone(self) -> tuple[Any, ...] | None:
        ...

    def fetchall(self) -> list[tuple[Any, ...]]:
        ...

    def __enter__(self) -> Self:
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        ...


class DatabaseConnection(Protocol):
    def cursor(self) -> DatabaseCursor:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...

    def close(self) -> None:
        ...


@dataclass(frozen=True)
class PostgresConfig:
    url: str


class DatabaseConnectionError(RuntimeError):
    pass


@contextmanager
def postgres_connection(settings: Settings) -> Iterator[DatabaseConnection]:
    try:
        psycopg = import_module("psycopg")
    except ModuleNotFoundError as exc:
        raise DatabaseConnectionError(
            "psycopg is required for live Postgres connections. Install backend dependencies first."
        ) from exc

    connection = psycopg.connect(settings.postgres_url)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
