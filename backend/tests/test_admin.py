"""Student Affairs screens, privacy and production safety."""
import csv
import io

import pytest

from tests.conftest import circle_of, me, signup, student, trip

from app.config import Settings, _db_url


def test_admin_only(client):
    h = student(client, 1)
    assert client.get("/api/admin/usage", headers=h).status_code == 403
    assert client.get("/api/admin/usage").status_code == 401


def test_approvals(client, admin):
    h = signup(client, 1, approve=False)
    p = client.get("/api/admin/approvals", headers=admin).json()
    assert len(p) == 1 and p[0]["programme"] == "BBA (Essex)" and p[0]["consent_version"]
    client.post(f"/api/admin/approvals/{p[0]['id']}", json={"approve": True}, headers=admin)
    assert me(client, h)["status"] == "approved"
    h2 = signup(client, 2, approve=False)
    uid = me(client, h2)["id"]
    client.post(f"/api/admin/approvals/{uid}", json={"approve": False}, headers=admin)
    assert client.get("/api/auth/me", headers=h2).status_code == 401
    r = client.post("/api/auth/login", data={"username": "s2@bic.edu.pk", "password": "password123"})
    assert r.status_code == 403


def test_usage_fares_health(client, admin):
    hs = [student(client, i) for i in range(1, 4)]
    student(client, 5, area="Clifton Block 5", days=("Tue",), arrive="13:00", leave="17:00")
    circle_of(client, hs)
    client.post("/api/today/yes", headers=hs[0])
    client.post("/api/today/fare", json={"share": 150}, headers=hs[0])
    u = client.get("/api/admin/usage", headers=admin).json()
    assert u["approved"] == 4 and u["in_circle"] == 3 and u["without"] == 1 and u["circles"] == 1
    assert any(a["area"] == "Clifton Block 5" and a["without"] == 1 for a in u["areas"])
    f = client.get("/api/admin/fares", headers=admin).json()
    assert f["fare_pct"] == 100
    h = client.get("/api/admin/health", headers=admin).json()
    assert h[0]["completed"] == 100 and h[0]["noshows"] == 0


def test_suspend_from_report(client, admin):
    hs = [student(client, i) for i in range(1, 4)]
    circle_of(client, hs)
    bad = me(client, hs[2])["id"]
    client.post("/api/circle/report", json={"reported_id": bad, "reason": "Repeatedly no-show", "leave": False}, headers=hs[0])
    rid = client.get("/api/admin/reports", headers=admin).json()["reports"][0]["id"]
    client.patch(f"/api/admin/reports/{rid}", json={"status": "suspended"}, headers=admin)
    assert client.get("/api/auth/me", headers=hs[2]).status_code == 401
    c = client.get("/api/circle", headers=hs[0]).json()
    assert c["status"] == "active" and bad not in [m["user_id"] for m in c["members"]]


def test_matching_lab(client, admin):
    for i in range(1, 6):
        student(client, i)
    res = client.post("/api/admin/compare", headers=admin).json()
    assert {r["algorithm"] for r in res} == {"greedy", "cluster", "compatibility"}
    assert client.get("/api/admin/circles", headers=admin).json() == []
    run = client.post("/api/admin/match", json={"algorithm": "compatibility"}, headers=admin).json()
    assert run["circles_created"] >= 1
    assert client.post("/api/admin/match", json={"algorithm": "greedy"}, headers=admin).json()["pool_size"] <= 1


def test_export_delete_and_research(client, admin):
    hs = [student(client, i) for i in range(1, 4)]
    client.patch("/api/auth/me", json={"research_consent": True}, headers=hs[0])
    circle_of(client, hs)
    exp = client.get("/api/auth/me/export", headers=hs[0]).json()
    assert exp["profile"]["area"] and exp["account"]["consent_version"] and exp["circles"]
    r = client.get("/api/admin/research-export", headers=admin)
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 1 and "@" not in r.text and "+92" not in r.text and "Khan" not in r.text
    assert client.request("DELETE", "/api/auth/me", json={"password": "nope"}, headers=hs[2]).status_code == 403
    assert client.request("DELETE", "/api/auth/me", json={"password": "password123"}, headers=hs[2]).status_code == 204
    c = client.get("/api/circle", headers=hs[0]).json()
    assert len(c["members"]) == 2


def test_login_throttle(client):
    signup(client, 1)
    for _ in range(5):
        client.post("/api/auth/login", data={"username": "s1@bic.edu.pk", "password": "wrong"})
    assert client.post("/api/auth/login", data={"username": "s1@bic.edu.pk", "password": "password123"}).status_code == 429


def test_bootstrap_admin(monkeypatch, client, db):
    from app.create_admin import bootstrap_admin
    from app.models import User

    monkeypatch.setenv("CC_ADMIN_EMAIL", "Affairs@bic.edu.pk")
    monkeypatch.setenv("CC_ADMIN_PASSWORD", "short")
    with pytest.raises(RuntimeError):
        bootstrap_admin()
    monkeypatch.setenv("CC_ADMIN_PASSWORD", "a-long-admin-password")
    bootstrap_admin()
    bootstrap_admin()
    assert db.query(User).filter_by(email="affairs@bic.edu.pk").count() == 1
    r = client.post("/api/auth/login", data={"username": "affairs@bic.edu.pk", "password": "a-long-admin-password"})
    assert r.status_code == 200
    assert client.get("/api/admin/usage", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).status_code == 200


def test_settings_guards(monkeypatch):
    assert _db_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    monkeypatch.setenv("CC_ENV", "production")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Settings().check()
    monkeypatch.setenv("CC_SECRET_KEY", "x" * 40)
    monkeypatch.setenv("CC_DATABASE_URL", "postgresql://u:p@h/db")
    Settings().check()


def test_seed_refuses_in_production(monkeypatch):
    import app.seed as seed_mod
    from app import config

    monkeypatch.setattr(seed_mod, "settings", config.Settings(env="production"))
    with pytest.raises(SystemExit):
        seed_mod.seed()


def test_v1_schema_with_students_is_never_wiped(tmp_path):
    from sqlalchemy import create_engine, text

    from app.migrate import migrate

    eng = create_engine(f"sqlite:///{tmp_path}/v1.db")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, full_name TEXT, password_hash TEXT, "
                       "role TEXT, is_active BOOLEAN)"))
        c.execute(text("INSERT INTO users VALUES (1, 's@bic.edu.pk', 'S', 'x', 'student', 1)"))
    with pytest.raises(RuntimeError, match="1 student accounts"):
        migrate(eng)
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM users")).scalar() == 1
