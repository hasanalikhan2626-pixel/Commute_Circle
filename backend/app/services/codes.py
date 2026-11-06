"""Email verification and password-reset codes."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import EmailCode, User
from . import notify

TTL = {"verify": timedelta(hours=24), "reset": timedelta(minutes=30)}
MAX_ATTEMPTS = 5
RESEND_AFTER = timedelta(seconds=60)


class CodeError(Exception):
    pass


def _hash(code: str) -> str:
    return hmac.new(settings.secret_key.encode(), code.encode(), hashlib.sha256).hexdigest()


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def send(db: Session, user: User, purpose: str) -> None:
    now = datetime.now(timezone.utc)
    last = db.scalar(select(EmailCode).where(EmailCode.user_id == user.id, EmailCode.purpose == purpose)
                     .order_by(EmailCode.id.desc()))
    if last and now - _aware(last.created_at) < RESEND_AFTER:
        raise CodeError("Please wait a minute before asking for another code")
    for old in db.scalars(select(EmailCode).where(EmailCode.user_id == user.id, EmailCode.purpose == purpose,
                                                  EmailCode.used.is_(False))):
        old.used = True  # only the newest code works
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(EmailCode(user_id=user.id, purpose=purpose, code_hash=_hash(code), expires_at=now + TTL[purpose]))
    first = user.full_name.split()[0]
    if purpose == "verify":
        subject, text = ("Your CommuteCircle verification code",
                         f"Hi {first},\n\nYour CommuteCircle code is {code}. It expires in 24 hours.\n\n"
                         "If you didn't sign up, you can ignore this email.")
    else:
        subject, text = ("Reset your CommuteCircle password",
                         f"Hi {first},\n\nYour password reset code is {code}. It expires in 30 minutes.\n\n"
                         "If you didn't ask for this, you can ignore this email; your password is unchanged.")
    notify.email(db, user.email, subject, text, user_id=user.id, template=f"code_{purpose}")
    db.flush()
    return code  # returned for tests and mock mode only; never sent to the browser


def check(db: Session, user: User, purpose: str, code: str) -> None:
    row = db.scalar(select(EmailCode).where(EmailCode.user_id == user.id, EmailCode.purpose == purpose,
                                            EmailCode.used.is_(False)).order_by(EmailCode.id.desc()))
    if not row or _aware(row.expires_at) < datetime.now(timezone.utc):
        raise CodeError("That code has expired. Ask for a new one.")
    if row.attempts >= MAX_ATTEMPTS:
        raise CodeError("Too many wrong attempts. Ask for a new code.")
    if not hmac.compare_digest(row.code_hash, _hash(code.strip())):
        row.attempts += 1
        db.commit()
        raise CodeError("That code isn't right")
    row.used = True
