"""SQLAlchemy engine / session factory.

SQLite is the development default; the model layer deliberately avoids any
SQLite-only construct so `DATABASE_URL` can point at PostgreSQL unchanged.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_url = settings.sqlalchemy_url
_is_sqlite = _url.startswith("sqlite")

engine: Engine = create_engine(
    _url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
    future=True,
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, _record):  # pragma: no cover - driver glue
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
