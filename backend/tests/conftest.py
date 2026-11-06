import os

os.environ.setdefault("CC_DATABASE_URL", "sqlite://")
os.environ["CC_EMAIL_DOMAINS"] = "bic.edu.pk"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, User  # noqa: E402
from app.security import hash_password, throttle  # noqa: E402

WEEK = {d: {"arrive": "08:30", "leave": "14:00"} for d in ("mon", "tue", "wed", "thu")}


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    throttle._fails.clear()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def register(client, n, **profile):
    r = client.post("/api/auth/register", json={
        "email": f"s{n}@bic.edu.pk", "password": "password123", "full_name": f"Student {n}", "phone": "0300 1234567",
        "consent": True, "research_consent": n % 2 == 0,
    })
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    body = {"area": "Gulshan-e-Iqbal", "gender": "female", "schedule": WEEK} | profile
    r = client.put("/api/profile", json=body, headers=h)
    assert r.status_code == 200, r.text
    return h


@pytest.fixture
def admin(client, db):
    db.add(User(email="admin@bic.edu.pk", full_name="Admin", role=Role.admin, password_hash=hash_password("adminpass1")))
    db.commit()
    r = client.post("/api/auth/login", data={"username": "admin@bic.edu.pk", "password": "adminpass1"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
