"""
database.py
-----------
SQLAlchemy engine/session factory.

Uses SQLite by default (file at database/colleges.db). Setting the
DATABASE_URL environment variable to a PostgreSQL URI lets the same code
run on Postgres without changes.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

try:
    from config import settings as _settings  # type: ignore
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    _default_sqlite = "sqlite:///" + os.path.join(
        BASE_DIR, "database", "colleges.db")
    # Empty DATABASE_URL in .env falls back to SQLite.
    DATABASE_URL = _settings.database_url or _default_sqlite
except Exception:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DEFAULT_SQLITE = "sqlite:///" + os.path.join(BASE_DIR, "database", "colleges.db")
    DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_SQLITE)

engine = create_engine(DATABASE_URL, future=True, echo=False,
                       connect_args={"check_same_thread": False}
                       if DATABASE_URL.startswith("sqlite") else {})

SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False,
                                           autocommit=False, future=True))
Base = declarative_base()


def init_db() -> None:
    """Create tables if they don't yet exist."""
    from models import College, Comparison, EloHistory  # noqa: F401
    os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)
    Base.metadata.create_all(bind=engine)


def reset_db() -> None:
    """Drop and recreate all tables (used by the ingestion rebuild).

    Safe: every row is re-derivable from the curated JSON + committed
    snapshots, so no real data is lost.
    """
    from models import College, Comparison, EloHistory  # noqa: F401
    os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
