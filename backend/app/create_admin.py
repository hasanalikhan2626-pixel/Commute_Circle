"""Create (or reset the password of) a transport-office admin account.

    python -m app.create_admin admin@bic.edu.pk "Transport Office"

Safe to run against production: it never deletes data. Prompts for the password.

Hosts without a shell (e.g. Render's free plan) can instead set CC_ADMIN_EMAIL and
CC_ADMIN_PASSWORD; ``bootstrap_admin`` then creates that admin once at startup.
"""
from __future__ import annotations

import getpass
import logging
import os
import sys

from sqlalchemy import select

from .db import Base, SessionLocal, engine
from .models import Role, User, UserStatus
from .security import hash_password


log = logging.getLogger("commutecircle")
MIN_ADMIN_PASSWORD = 12


def bootstrap_admin() -> None:
    """Create the admin named in CC_ADMIN_EMAIL/CC_ADMIN_PASSWORD if it does not exist.

    Never changes an existing account, so leaving the variables set is harmless,
    but removing CC_ADMIN_PASSWORD after the first login is good practice.
    """
    email = os.environ.get("CC_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("CC_ADMIN_PASSWORD", "")
    if not email or not password:
        return
    if len(password) < MIN_ADMIN_PASSWORD:
        raise RuntimeError(f"CC_ADMIN_PASSWORD must be at least {MIN_ADMIN_PASSWORD} characters")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            return
        db.add(User(email=email, full_name="Student Affairs", role=Role.admin, status=UserStatus.approved,
                    password_hash=hash_password(password)))
        db.commit()
        log.warning("Created admin account %s from CC_ADMIN_EMAIL", email)


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        raise SystemExit(__doc__)
    email, name = argv[1].strip().lower(), (argv[2] if len(argv) > 2 else "Transport Office")
    pw = getpass.getpass("Password (min 12 chars): ")
    if len(pw) < MIN_ADMIN_PASSWORD or pw != getpass.getpass("Repeat: "):
        raise SystemExit(f"Passwords must match and be at least {MIN_ADMIN_PASSWORD} characters.")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        if u:
            u.password_hash, u.role, u.status = hash_password(pw), Role.admin, UserStatus.approved
            print(f"Updated {email} (now admin).")
        else:
            db.add(User(email=email, full_name=name, role=Role.admin, status=UserStatus.approved,
                        password_hash=hash_password(pw)))
            print(f"Created admin {email}.")
        db.commit()


if __name__ == "__main__":
    main(sys.argv)
