"""Consent, data access, erasure and research export (needed before collecting real data)."""
import csv
import io

from tests.conftest import register

from app.config import Settings, _db_url


def test_profile_is_null_before_setup(client):
    r = client.post("/api/auth/register", json={"email": "n@bic.edu.pk", "password": "password123",
                                                 "full_name": "New One", "consent": True})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.get("/api/profile", headers=h)
    assert r.status_code == 200 and r.json() is None


def test_registration_requires_consent(client):
    body = {"email": "a@bic.edu.pk", "password": "password123", "full_name": "No Consent"}
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 422 and "privacy notice" in r.text
    assert client.post("/api/auth/register", json=body | {"consent": True}).status_code == 201


def test_consent_recorded_and_research_toggle(client):
    h = register(client, 1)
    me = client.get("/api/auth/me", headers=h).json()
    assert me["research_consent"] is False
    me = client.patch("/api/auth/me", json={"research_consent": True}, headers=h).json()
    assert me["research_consent"] is True
    exp = client.get("/api/auth/me/export", headers=h).json()
    assert exp["account"]["consent_version"] and exp["account"]["consented_at"]
    assert exp["profile"]["area"] == "Gulshan-e-Iqbal"


def test_delete_account_leaves_circle_and_keeps_reports(client, admin):
    d = register(client, 1, has_car=True, seats=3)
    r1, r2 = register(client, 2), register(client, 3)
    client.post("/api/admin/match", json={}, headers=admin)
    cid = client.get("/api/circles/mine", headers=r1).json()[0]["id"]
    for h in (d, r1, r2):
        client.post(f"/api/circles/{cid}/respond", json={"accept": True}, headers=h)
    r2_id = client.get("/api/auth/me", headers=r2).json()["id"]
    client.post("/api/reports", json={"reported_id": r2_id, "reason": "no_show"}, headers=r1)

    assert client.request("DELETE", "/api/auth/me", json={"password": "wrong"}, headers=r2).status_code == 403
    assert client.request("DELETE", "/api/auth/me", json={"password": "password123"}, headers=r2).status_code == 204
    assert client.get("/api/auth/me", headers=r2).status_code == 401
    c = client.get(f"/api/circles/{cid}", headers=r1).json()
    assert c["status"] == "active" and r2_id not in [m["user_id"] for m in c["members"]]
    rep = client.get("/api/admin/reports", headers=admin).json()[0]
    assert rep["reported_id"] is None, "report survives, but no longer identifies the deleted user"


def test_research_export_only_consenting_and_pseudonymised(client, admin):
    for n in range(1, 5):  # even n opt in to research (see conftest)
        register(client, n)
    r = client.get("/api/admin/research-export", headers=admin)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 2
    assert "Student" not in r.text and "@" not in r.text and "+92" not in r.text
    assert all(len(row["pid"]) == 10 for row in rows)


def test_database_url_normalised():
    assert _db_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert _db_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert _db_url("sqlite:///x.db") == "sqlite:///x.db"


def test_production_refuses_unsafe_settings(monkeypatch):
    import pytest

    monkeypatch.setenv("CC_ENV", "production")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Settings().check()
    monkeypatch.setenv("CC_SECRET_KEY", "x" * 40)
    monkeypatch.setenv("CC_DATABASE_URL", "sqlite:///x.db")
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        Settings().check()
    monkeypatch.setenv("CC_DATABASE_URL", "postgresql://u:p@h/db")
    Settings().check()
