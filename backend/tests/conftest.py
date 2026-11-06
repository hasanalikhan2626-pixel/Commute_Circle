import os
from datetime import date

os.environ.setdefault("CC_DATABASE_URL", "sqlite://")
os.environ["CC_EMAIL_DOMAINS"] = "bic.edu.pk"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, User, UserStatus  # noqa: E402
from app.security import hash_password, throttle  # noqa: E402
from app.services import clock  # noqa: E402

MONDAY = date(2026, 11, 9)
SH, CD = "Shared ride-hailing", "Classmate drives"
NAMES = ["Ayesha Khan", "Hira Siddiqui", "Iqra Farooq", "Zainab Raza", "Mahnoor Ali", "Sana Javed", "Ali Hassan",
         "Usman Tariq", "Bilal Ahmed", "Hamza Qureshi"]


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    throttle._fails.clear()
    clock.set_today(MONDAY)
    yield
    clock.set_today(None)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def signup(client, n, gender="female", approve=True, research=False):
    r = client.post("/api/auth/register", json={
        "email": f"s{n}@bic.edu.pk", "password": "password123", "full_name": NAMES[n % len(NAMES)],
        "phone": "0300 1234567", "gender": gender, "programme": "BBA (Essex)", "year": 2,
        "consent": True, "research_consent": research})
    assert r.status_code == 201, r.text
    h = auth(r.json()["access_token"])
    if approve:
        with SessionLocal() as s:
            u = s.query(User).filter_by(email=f"s{n}@bic.edu.pk").one()
            u.status = UserStatus.approved
            s.commit()
    return h


def trip(client, h, area="Gulshan-e-Iqbal Block 13", days=("Mon", "Tue", "Wed", "Thu", "Fri"), arrive="08:30",
         leave="14:00", methods=(SH,), **kw):
    r = client.put("/api/trip", json={"area": area, "days": list(days), "arrive": arrive, "leave": leave,
                                      "methods": list(methods), **kw}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def student(client, n, gender="female", **kw):
    h = signup(client, n, gender)
    trip(client, h, **kw)
    return h


def me(client, h):
    return client.get("/api/auth/me", headers=h).json()


def circle_of(client, hs, n=None):
    """Student hs[0] picks the first option; everyone else accepts. Returns the circle."""
    opts = client.get("/api/find/options", headers=hs[0]).json()["options"]
    ids = opts[0]["member_ids"][: n or 4]
    assert client.post("/api/find/accept", json={"member_ids": ids}, headers=hs[0]).status_code == 200
    for h in hs[1:]:
        if me(client, h)["id"] in ids:
            assert client.post("/api/circle/respond", json={"accept": True}, headers=h).status_code == 200
    return client.get("/api/circle", headers=hs[0]).json()


@pytest.fixture
def admin(client, db):
    db.add(User(email="admin@bic.edu.pk", full_name="Student Affairs", role=Role.admin, status=UserStatus.approved,
                password_hash=hash_password("adminpass1")))
    db.commit()
    r = client.post("/api/auth/login", data={"username": "admin@bic.edu.pk", "password": "adminpass1"})
    return auth(r.json()["access_token"])
