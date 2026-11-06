"""Bring the database schema up to date on startup (Alembic).

Three cases:
* Empty database: create everything with the migrations.
* A database built by ``create_all`` (dev seed, tests): mark it as current.
* The v1 schema (before the prototype redesign, Nov 2026): if it holds no student
  accounts, rebuild it and carry the admin logins across; otherwise refuse to
  start rather than risk losing data.
"""
from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, inspect, text
from sqlalchemy.engine import Engine

log = logging.getLogger("commutecircle")
ROOT = Path(__file__).resolve().parent.parent
V1_ENUMS = ("role", "gender", "circlestatus", "memberstatus", "reportstatus")


def _config(connection) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["connection"] = connection
    return cfg


def _is_v1(insp) -> bool:
    return "users" in insp.get_table_names() and "is_active" in {c["name"] for c in insp.get_columns("users")}


def _replace_v1(engine: Engine) -> list[dict]:
    with engine.begin() as conn:
        students = conn.execute(text("SELECT count(*) FROM users WHERE role = 'student'")).scalar()
        if students:
            raise RuntimeError(
                f"The database uses the old v1 schema and holds {students} student accounts. "
                "Back it up and migrate it by hand before starting this version.")
        admins = [dict(r._mapping) for r in conn.execute(
            text("SELECT email, full_name, password_hash FROM users WHERE role = 'admin'"))]
        meta = MetaData()
        meta.reflect(bind=conn)
        meta.drop_all(bind=conn)
        if conn.dialect.name == "postgresql":
            for t in V1_ENUMS:
                conn.execute(text(f'DROP TYPE IF EXISTS "{t}" CASCADE'))
    log.warning("Replaced the v1 schema (no student data); kept %d admin login(s)", len(admins))
    return admins


def migrate(engine: Engine) -> None:
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    admins: list[dict] = []
    if _is_v1(insp):
        admins = _replace_v1(engine)
        tables = set()
    with engine.begin() as conn:
        cfg = _config(conn)
        if tables and "alembic_version" not in tables:
            command.stamp(cfg, "head")  # created by create_all: already current
        else:
            command.upgrade(cfg, "head")
    if admins:
        from .db import SessionLocal
        from .models import Role, User, UserStatus

        with SessionLocal() as db:
            for a in admins:
                db.add(User(email=a["email"], full_name=a["full_name"], password_hash=a["password_hash"],
                            role=Role.admin, status=UserStatus.approved))
            db.commit()
