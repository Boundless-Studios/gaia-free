"""Database utility functions for SQLAlchemy models."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import String as SAString

try:
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
except ImportError:  # pragma: no cover - fallback for environments without dialect
    PG_UUID = None  # type: ignore


def _uuid_column(**kwargs) -> Mapped[uuid.UUID]:
    """Helper to create UUID columns compatible with Postgres + SQLite."""
    if PG_UUID:
        column_type = PG_UUID(as_uuid=True)
        default_factory = uuid.uuid4
    else:
        column_type = SAString(36)
        default_factory = lambda: str(uuid.uuid4())
    return mapped_column(
        column_type,
        default=default_factory,
        nullable=False,
        **kwargs,
    )
