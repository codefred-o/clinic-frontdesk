"""SQLAlchemy 2.0 declarative base shared by all ORM models."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase

from app.db.mixins import TimestampMixin as TimestampMixin


class Base(DeclarativeBase):
    """Project-wide declarative base. Import this to build ORM models."""
