"""SQLAlchemy 2.0 ORM base + shared helpers for Phase 20."""

from __future__ import annotations

from datetime import datetime, timezone

import ulid
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Common ORM base. All Record subclasses inherit from this."""


def new_ulid() -> str:
    """Factory for 26-char ULID primary keys."""
    return str(ulid.ULID())


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp. Use as ``default=utcnow`` on DateTime columns."""
    return datetime.now(timezone.utc)
