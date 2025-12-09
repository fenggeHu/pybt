"""Database setup for backend services.

SQLite is the default, but any SQLAlchemy-supported database can be used by
setting the PYBT_DATABASE_URL environment variable (e.g. PostgreSQL/MySQL).
"""

from __future__ import annotations

import os
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATABASE_URL = os.environ.get("PYBT_DATABASE_URL", "sqlite:///./pybt.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)
Base = declarative_base()


def get_session() -> Iterator[Session]:
    """FastAPI dependency for acquiring a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if they do not exist."""
    # Import models so metadata is populated before create_all
    from . import rbac as _  # noqa: F401

    Base.metadata.create_all(bind=engine)
