from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, Request

from .db import fetch_one


def hash_password(plain_password: str) -> str:
    # bcrypt has a 72-byte limit; enforce explicitly for predictable behavior.
    pw = plain_password.encode("utf-8")
    if len(pw) > 72:
        pw = pw[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, password_hash: str | bytes) -> bool:
    # Works for bcrypt hashes produced by PostgreSQL `crypt(..., gen_salt('bf'))`
    # and by `hash_password()` above.
    try:
        pw = plain_password.encode("utf-8")
        if len(pw) > 72:
            pw = pw[:72]
        if isinstance(password_hash, memoryview):
            password_hash = password_hash.tobytes()

        if isinstance(password_hash, bytes):
            hashed = password_hash
        else:
            hashed = password_hash.encode("utf-8")

        return bcrypt.checkpw(pw, hashed)
    except Exception:
        return False


def ensure_csrf_token(session: dict[str, Any]) -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def check_csrf(request: Request, submitted: str | None) -> None:
    session = request.session
    expected = session.get("csrf_token")
    if not expected:
        raise HTTPException(status_code=403, detail="missing_csrf")

    if not submitted or not secrets.compare_digest(expected, submitted):
        raise HTTPException(status_code=403, detail="bad_csrf")


@dataclass(frozen=True)
class CurrentUser:
    user_id: int
    email: str
    username: str
    nickname: str | None


async def current_user(request: Request) -> CurrentUser:
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="not_authenticated")

    pool = request.app.state.db_pool
    async with pool.connection() as conn:
        row = await fetch_one(
            conn,
            "SELECT user_id, email, username, nickname FROM users WHERE user_id = %s",
            [uid],
        )
    if not row:
        request.session.clear()
        raise HTTPException(status_code=401, detail="not_authenticated")

    return CurrentUser(
        user_id=row["user_id"],
        email=row["email"],
        username=row["username"],
        nickname=row["nickname"],
    )


# Very small demo-grade rate limiter (memory only)
class LoginRateLimiter:
    def __init__(self, window_seconds: int = 300, max_attempts: int = 10) -> None:
        self.window = window_seconds
        self.max_attempts = max_attempts
        self._buckets: dict[str, list[float]] = {}

    def _now(self) -> float:
        return time.time()

    def allow(self, key: str) -> bool:
        now = self._now()
        bucket = self._buckets.get(key, [])
        bucket = [t for t in bucket if now - t < self.window]
        if len(bucket) >= self.max_attempts:
            self._buckets[key] = bucket
            return False
        bucket.append(now)
        self._buckets[key] = bucket
        return True


def require_user(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    return user

