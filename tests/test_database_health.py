"""Database readiness probe tests."""

from __future__ import annotations

from sqlalchemy.exc import OperationalError

from app.db.health import database_is_ready


class ConnectionContext:
    def __init__(self, connection=None, error: Exception | None = None) -> None:
        self.connection = connection
        self.error = error

    async def __aenter__(self):
        if self.error:
            raise self.error
        return self.connection

    async def __aexit__(self, *_args) -> None:
        return None


class Connection:
    def __init__(self) -> None:
        self.queries = []

    async def execute(self, query) -> None:
        self.queries.append(str(query))


class Engine:
    def __init__(self, context: ConnectionContext) -> None:
        self.context = context

    def connect(self) -> ConnectionContext:
        return self.context


async def test_database_ready_executes_minimal_query() -> None:
    connection = Connection()

    result = await database_is_ready(Engine(ConnectionContext(connection)))  # type: ignore[arg-type]

    assert result is True
    assert connection.queries == ["SELECT 1"]


async def test_database_ready_handles_sqlalchemy_failure() -> None:
    error = OperationalError("SELECT 1", {}, Exception("offline"))

    result = await database_is_ready(Engine(ConnectionContext(error=error)))  # type: ignore[arg-type]

    assert result is False
