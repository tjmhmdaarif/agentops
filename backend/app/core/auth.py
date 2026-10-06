"""Authentication — DB-backed sessions in httpOnly cookies.

Deliberately small: PBKDF2 password hashing (stdlib), opaque session tokens
stored in SQLite (revocable), no JWT library required. /api/health and the
login endpoint stay public (platform health checks); everything else under
/api requires a valid session cookie.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.logging import get_logger
from app.db.database import Base, Database

log = get_logger("auth")

SESSION_COOKIE = "agentops_session"
SESSION_TTL_S = 7 * 24 * 3600
PBKDF2_ITERATIONS = 120_000


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    salt: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    role: Mapped[str] = mapped_column(String(16), default="admin")


class Session(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(96), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    expires_at: Mapped[float] = mapped_column(Float)


def hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return digest.hex()


class AuthService:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------ users
    def ensure_admin(self, username: str, password: str) -> None:
        """Seed the initial admin account if the user table is empty."""
        with self.db.session() as s:
            if s.query(User).count() > 0:
                return
            salt = secrets.token_hex(16)
            s.add(User(
                username=username,
                password_hash=hash_password(password, salt),
                salt=salt,
                role="admin",
            ))
        log.info("admin_user_seeded username=%s", username)

    def verify(self, username: str, password: str) -> bool:
        with self.db.session() as s:
            user = s.query(User).filter_by(username=username).first()
            if user is None:
                return False
            candidate = hash_password(password, user.salt)
            return hmac.compare_digest(candidate, user.password_hash)

    # --------------------------------------------------------------- sessions
    def create_session(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self.db.session() as s:
            # Opportunistic cleanup of expired sessions.
            s.query(Session).filter(Session.expires_at < now).delete()
            s.add(Session(token=token, username=username,
                          created_at=now, expires_at=now + SESSION_TTL_S))
        return token

    def resolve(self, token: str | None) -> str | None:
        """Token → username, or None when invalid/expired."""
        if not token:
            return None
        with self.db.session() as s:
            session = s.get(Session, token)
            if session is None or session.expires_at < time.time():
                return None
            return session.username

    def revoke(self, token: str | None) -> None:
        if not token:
            return
        with self.db.session() as s:
            s.query(Session).filter_by(token=token).delete()

    def change_password(self, username: str, new_password: str) -> None:
        with self.db.session() as s:
            user = s.query(User).filter_by(username=username).first()
            if user is None:
                return
            salt = secrets.token_hex(16)
            user.salt = salt
            user.password_hash = hash_password(new_password, salt)
            # Force re-login everywhere else.
            s.query(Session).filter(Session.username == username).delete()
