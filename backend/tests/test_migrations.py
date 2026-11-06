"""The Alembic migrations must build exactly the schema the models describe.

Tests build tables with create_all, so without this check a model change without a
migration would pass CI and then fail on the live database at start-up.
"""
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

from app.db import Base
from app.migrate import migrate


def test_migrations_match_models(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/m.db")
    migrate(eng)  # empty database -> upgrade to head
    with eng.connect() as c:
        diff = compare_metadata(MigrationContext.configure(c), Base.metadata)
    assert diff == [], f"Models changed without a migration: {diff}"


def test_upgrade_keeps_existing_rows(tmp_path):
    from alembic import command

    from app.migrate import _config

    eng = create_engine(f"sqlite:///{tmp_path}/u.db")
    with eng.begin() as c:
        command.upgrade(_config(c), "0001")
        c.execute(text("INSERT INTO users (email, password_hash, full_name, role, status, created_at, research_consent) "
                       "VALUES ('a@bic.edu.pk', 'x', 'A B', 'admin', 'approved', CURRENT_TIMESTAMP, 0)"))
    migrate(eng)  # 0001 with data -> head
    with eng.connect() as c:
        row = c.execute(text("SELECT email, email_verified, whatsapp_opt_in FROM users")).one()
    assert row == ("a@bic.edu.pk", 0, 0)
