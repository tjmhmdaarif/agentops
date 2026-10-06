"""Database engine / session management."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_parent_dir(url: str) -> None:
    """Create the SQLite file's parent directory if missing.

    `sqlite:///./data/x.db` resolves against the process CWD, which differs
    between dev (backend/) and the Docker image (/app/backend). Rather than
    depend on the deploy layout, guarantee the directory exists.
    """
    if not url.startswith("sqlite") or ":memory:" in url or "///" not in url:
        return
    raw = url.split("///", 1)[1]
    if not raw:
        return
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)


class Database:
    """Thin wrapper around the SQLAlchemy engine + session factory."""

    def __init__(self, settings: Settings) -> None:
        url = settings.database_url
        _ensure_sqlite_parent_dir(url)
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        from app.db import models  # noqa: F401  (register tables)
        Base.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        from app.db import models  # noqa: F401
        Base.metadata.drop_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
