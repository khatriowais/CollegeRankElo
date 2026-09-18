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
