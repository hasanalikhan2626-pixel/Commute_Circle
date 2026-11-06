from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(p: str) -> str:
    return _pwd.hash(p)


def verify_password(p: str, h: str) -> bool:
    return _pwd.verify(p, h)


def create_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> int | None:
    try:
        return int(jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])["sub"])
    except (JWTError, KeyError, ValueError):
        return None


class LoginThrottle:
    """Blocks an email after ``limit`` failed logins inside ``window`` seconds.

    In-memory, so per process; swap for Redis when running several workers.
    """

    def __init__(self, limit: int = 5, window: int = 900):
        self.limit, self.window = limit, window
        self._fails: dict[str, deque[float]] = defaultdict(deque)

    def _trim(self, key: str) -> deque[float]:
        q, now = self._fails[key], time.monotonic()
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def blocked(self, key: str) -> bool:
        return len(self._trim(key)) >= self.limit

    def fail(self, key: str) -> None:
        self._trim(key).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._fails.pop(key, None)


throttle = LoginThrottle()
