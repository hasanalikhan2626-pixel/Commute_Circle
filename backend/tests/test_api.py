"""End-to-end API tests covering the student and admin journeys."""
from datetime import date, timedelta

from tests.conftest import WEEK, register

from app.models import Circle, CircleStatus, RotaEntry
from app.services import rota


def test_register_validates_domain_and_phone(client):
    r = client.post("/api/auth/register", json={"email": "x@gmail.com", "password": "password123", "full_name": "X"})
    assert r.status_code == 422
    r = client.post("/api/auth/register", json={"email": "x@bic.edu.pk", "password": "password123",
                                                 "full_name": "X", "phone": "12345"})
    assert r.status_code == 422


def test_phone_normalised(client):
    h = register(client, 1)
    assert client.get("/api/auth/me", headers=h).json()["phone"] == "+923001234567"


def test_duplicate_email(client):
    register(client, 1)
    r = client.post("/api/auth/register", json={"email": "S1@bic.edu.pk", "password": "password123", "full_name": "Dup User"})
    assert r.status_code == 409


def test_login_throttle(client):
    register(client, 1)
    for _ in range(5):
        assert client.post("/api/auth/login", data={"username": "s1@bic.edu.pk", "password": "wrong"}).status_code == 401
    r = client.post("/api/auth/login", data={"username": "s1@bic.edu.pk", "password": "password123"})
    assert r.status_code == 429


def test_profile_validation(client):
    h = register(client, 1)
    bad = {"area": "Atlantis", "schedule": WEEK}
    assert client.put("/api/profile", json=bad, headers=h).status_code == 422
    bad = {"area": "PECHS", "schedule": {"mon": {"arrive": "14:00", "leave": "09:00"}}}
    assert client.put("/api/profile", json=bad, headers=h).status_code == 422
    bad = {"area": "PECHS", "has_car": True, "seats": 0, "schedule": WEEK}
    assert client.put("/api/profile", json=bad, headers=h).status_code == 422


def test_admin_only(client):
    h = register(client, 1)
    assert client.get("/api/admin/stats", headers=h).status_code == 403
    assert client.get("/api/admin/stats").status_code == 401


def _make_group(client):
    d = register(client, 1, has_car=True, seats=3)
    r1 = register(client, 2)
    r2 = register(client, 3)
    return d, r1, r2


def test_full_journey_accept(client, admin):
    d, r1, r2 = _make_group(client)
    run = client.post("/api/admin/match", json={"algorithm": "compatibility"}, headers=admin).json()
    assert run["circles_created"] == 1 and run["students_matched"] == 3

    c = client.get("/api/circles/mine", headers=r1).json()[0]
    assert c["status"] == "proposed"
    assert all(m["phone"] is None for m in c["members"]), "contacts hidden before activation"

    for h in (d, r1, r2):
        c = client.post(f"/api/circles/{c['id']}/respond", json={"accept": True}, headers=h).json()
    assert c["status"] == "active"
    assert all(m["phone"] for m in c["members"]), "contacts revealed once active"
    assert c["rota"] and all(e["driver_id"] for e in c["rota"])
    assert c["costs"]["available"] and c["costs"]["per_member"]


def test_rematching_does_not_touch_profiles_or_circles(client, admin):
    """Regression for prototype bug: re-running matching overwrote profiles."""
    d, r1, r2 = _make_group(client)
    before = client.get("/api/profile", headers=r1).json()
    client.post("/api/admin/match", json={}, headers=admin)
    first = client.get("/api/circles/mine", headers=r1).json()
    run2 = client.post("/api/admin/match", json={"algorithm": "greedy"}, headers=admin).json()
    assert run2["circles_created"] == 0 and run2["pool_size"] == 0
    assert client.get("/api/profile", headers=r1).json() == before
    assert client.get("/api/circles/mine", headers=r1).json() == first


def test_decline_remembers_pair_and_dissolves_if_unviable(client, admin):
    d = register(client, 1, has_car=True, seats=3)
    r = register(client, 2)
    client.post("/api/admin/match", json={}, headers=admin)
    cid = client.get("/api/circles/mine", headers=r).json()[0]["id"]
    c = client.post(f"/api/circles/{cid}/respond", json={"accept": False}, headers=r).json()
    assert c["status"] == "dissolved"
    # The same pair is not proposed again.
    run = client.post("/api/admin/match", json={}, headers=admin).json()
    assert run["pool_size"] == 2 and run["circles_created"] == 0


def test_decline_keeps_viable_circle(client, admin):
    d, r1, r2 = _make_group(client)
    client.post("/api/admin/match", json={}, headers=admin)
    cid = client.get("/api/circles/mine", headers=r1).json()[0]["id"]
    client.post(f"/api/circles/{cid}/respond", json={"accept": False}, headers=r2)
    client.post(f"/api/circles/{cid}/respond", json={"accept": True}, headers=d)
    c = client.post(f"/api/circles/{cid}/respond", json={"accept": True}, headers=r1).json()
    assert c["status"] == "active" and len(c["members"]) == 2
    assert client.get(f"/api/circles/{cid}", headers=r2).json()["my_status"] == "declined"


def test_driver_leaving_dissolves(client, admin):
    d, r1, r2 = _make_group(client)
    client.post("/api/admin/match", json={}, headers=admin)
    cid = client.get("/api/circles/mine", headers=r1).json()[0]["id"]
    for h in (d, r1, r2):
        client.post(f"/api/circles/{cid}/respond", json={"accept": True}, headers=h)
    c = client.post(f"/api/circles/{cid}/leave", headers=d).json()
    assert c["status"] == "dissolved"
    # Riders return to the matching pool.
    assert client.get("/api/admin/stats", headers=admin).json()["seeking_unmatched"] == 3


def test_circle_privacy(client, admin):
    d, r1, r2 = _make_group(client)
    outsider = register(client, 9, area="Malir")
    client.post("/api/admin/match", json={}, headers=admin)
    cid = client.get("/api/circles/mine", headers=r1).json()[0]["id"]
    assert client.get(f"/api/circles/{cid}", headers=outsider).status_code == 404
    me = client.get("/api/auth/me", headers=outsider).json()
    r = client.post("/api/reports", json={"reported_id": me["id"] - 1, "reason": "other"}, headers=outsider)
    assert r.status_code == 403


def test_rota_is_fair_between_drivers(client, admin, db):
    """Regression for prototype bug: the first driver was always assigned."""
    a = register(client, 1, has_car=True, seats=3)
    b = register(client, 2, has_car=True, seats=3)
    c = register(client, 3)
    client.post("/api/admin/match", json={}, headers=admin)
    cid = client.get("/api/circles/mine", headers=c).json()[0]["id"]
    for h in (a, b, c):
        circle = client.post(f"/api/circles/{cid}/respond", json={"accept": True}, headers=h).json()
    counts = {}
    for e in circle["rota"]:
        counts[e["driver_id"]] = counts.get(e["driver_id"], 0) + 1
    assert len(counts) == 2 and max(counts.values()) - min(counts.values()) <= 1

    # History carries over: regenerating a week later keeps the balance.
    obj = db.get(Circle, cid)
    rota.regenerate(db, obj, today=date.today() + timedelta(days=7))
    db.commit()
    totals = {}
    for e in db.query(RotaEntry).filter_by(circle_id=cid):
        totals[e.driver_id] = totals.get(e.driver_id, 0) + 1
    assert max(totals.values()) - min(totals.values()) <= 1


def test_driver_unavailable_reassigns(client, admin):
    a = register(client, 1, has_car=True, seats=3)
    b = register(client, 2, has_car=True, seats=3)
    c = register(client, 3)
    client.post("/api/admin/match", json={}, headers=admin)
    cid = client.get("/api/circles/mine", headers=c).json()[0]["id"]
    for h in (a, b, c):
        circle = client.post(f"/api/circles/{cid}/respond", json={"accept": True}, headers=h).json()
    entry = circle["rota"][0]
    hdr = a if client.get("/api/auth/me", headers=a).json()["id"] == entry["driver_id"] else b
    circle = client.post(f"/api/circles/{cid}/unavailable", json={"day": entry["day"]}, headers=hdr).json()
    new = next(e for e in circle["rota"] if e["day"] == entry["day"])
    assert new["driver_id"] != entry["driver_id"]


def test_suspending_user_removes_from_circle(client, admin):
    d, r1, r2 = _make_group(client)
    client.post("/api/admin/match", json={}, headers=admin)
    cid = client.get("/api/circles/mine", headers=r1).json()[0]["id"]
    for h in (d, r1, r2):
        client.post(f"/api/circles/{cid}/respond", json={"accept": True}, headers=h)
    uid = client.get("/api/auth/me", headers=r2).json()["id"]
    assert client.patch(f"/api/admin/users/{uid}", json={"is_active": False}, headers=admin).status_code == 200
    c = client.get(f"/api/circles/{cid}", headers=r1).json()
    assert c["status"] == "active" and uid not in [m["user_id"] for m in c["members"]]
    assert client.get("/api/auth/me", headers=r2).status_code == 401


def test_report_flow(client, admin):
    d, r1, r2 = _make_group(client)
    client.post("/api/admin/match", json={}, headers=admin)
    did = client.get("/api/auth/me", headers=d).json()["id"]
    assert client.post("/api/reports", json={"reported_id": did, "reason": "unsafe_driving", "details": "speeding"},
                       headers=r1).status_code == 201
    reports = client.get("/api/admin/reports", headers=admin).json()
    assert reports[0]["reported_name"] == "Student 1"
    r = client.patch(f"/api/admin/reports/{reports[0]['id']}", json={"status": "resolved", "admin_note": "Spoke to driver"},
                     headers=admin)
    assert r.json()["status"] == "resolved"


def test_compare_is_dry_run(client, admin, db):
    _make_group(client)
    res = client.post("/api/admin/compare", headers=admin).json()
    assert {r["algorithm"] for r in res} == {"greedy", "cluster", "compatibility"}
    assert db.query(Circle).count() == 0


def test_profile_change_warns_when_circle_breaks(client, admin):
    d = register(client, 1, has_car=True, seats=3)
    r = register(client, 2)
    client.post("/api/admin/match", json={}, headers=admin)
    cid = client.get("/api/circles/mine", headers=r).json()[0]["id"]
    for h in (d, r):
        client.post(f"/api/circles/{cid}/respond", json={"accept": True}, headers=h)
    res = client.put("/api/profile", json={"area": "Gulshan-e-Iqbal", "schedule": {"fri": {"arrive": "12:00", "leave": "15:00"}}},
                     headers=r).json()
    assert res["warning"]
