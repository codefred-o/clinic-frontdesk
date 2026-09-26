"""Database availability checks used by operational endpoints."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine


async def database_is_ready(engine: AsyncEngine) -> bool:
    """Return whether the database accepts a minimal query."""

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True
