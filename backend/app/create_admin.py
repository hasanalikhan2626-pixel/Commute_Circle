"""Create (or reset the password of) a transport-office admin account.

    python -m app.create_admin admin@bic.edu.pk "Transport Office"

Safe to run against production: it never deletes data. Prompts for the password.
"""
from __future__ import annotations

import getpass
import sys

from sqlalchemy import select

from .db import Base, SessionLocal, engine
from .models import Role, User
from .security import hash_password


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        raise SystemExit(__doc__)
    email, name = argv[1].strip().lower(), (argv[2] if len(argv) > 2 else "Transport Office")
    pw = getpass.getpass("Password (min 12 chars): ")
    if len(pw) < 12 or pw != getpass.getpass("Repeat: "):
        raise SystemExit("Passwords must match and be at least 12 characters.")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        if u:
            u.password_hash, u.role, u.is_active = hash_password(pw), Role.admin, True
            print(f"Updated {email} (now admin).")
        else:
            db.add(User(email=email, full_name=name, role=Role.admin, password_hash=hash_password(pw)))
            print(f"Created admin {email}.")
        db.commit()


if __name__ == "__main__":
    main(sys.argv)
