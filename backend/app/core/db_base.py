"""Base declarativa compartilhada pelos modelos SQLAlchemy."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
