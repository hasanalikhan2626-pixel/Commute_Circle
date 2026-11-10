"""Student journeys, mirroring the prototype tabs."""
from datetime import timedelta

from tests.conftest import CD, MONDAY, SH, circle_of, me, signup, student, trip

from app.services import clock


def test_signup_validation(client):
    base = {"password": "password123", "full_name": "Ayesha Khan", "phone": "0300 1234567", "gender": "female",
            "programme": "BBA (Essex)", "year": 1, "consent": True}
    assert client.post("/api/auth/register", json=base | {"email": "a@gmail.com"}).status_code == 422
    assert client.post("/api/auth/register", json=base | {"email": "a@bic.edu.pk", "consent": False}).status_code == 422
    assert client.post("/api/auth/register", json=base | {"email": "a@bic.edu.pk", "full_name": "Ayesha"}).status_code == 422
    r = client.post("/api/auth/register", json=base | {"email": "A@BIC.edu.pk"})
    assert r.status_code == 201
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    u = client.get("/api/auth/me", headers=h).json()
    assert u["email"] == "a@bic.edu.pk" and u["status"] == "pending" and u["phone"] == "+923001234567"
    dup = base | {"email": "b@bic.edu.pk"}
    assert client.post("/api/auth/register", json=dup).status_code == 409  # same mobile number


def test_pending_students_cannot_match(client):
    h = signup(client, 1, approve=False)
    trip(client, h)
    r = client.get("/api/find/options", headers=h)
    assert r.status_code == 409 and "approval" in r.json()["detail"]


def test_trip_questions_validation(client):
    h = signup(client, 1)
    bad = {"area": "Atlantis", "days": ["Mon"], "arrive": "08:30", "leave": "14:00", "methods": [SH]}
    assert client.put("/api/trip", json=bad, headers=h).status_code == 422
    bad = bad | {"area": "Saddar", "arrive": "15:00"}
    assert client.put("/api/trip", json=bad, headers=h).status_code == 422
    bad = bad | {"arrive": "08:30", "days": ["Sat"]}
    assert client.put("/api/trip", json=bad, headers=h).status_code == 422
    # Men cannot set women-only; it is ignored.
    hm = signup(client, 2, gender="male")
    trip(client, hm, women_only=True)
    assert client.get("/api/trip", headers=hm).json()["women_only"] is False


def test_find_options_and_accept_flow(client):
    hs = [student(client, i) for i in range(1, 5)]
    opts = client.get("/api/find/options", headers=hs[0]).json()["options"]
    assert opts and opts[0]["fit"] >= 45 and opts[0]["members"][0]["pickup"] == 1
    assert any(m["me"] for m in opts[0]["members"])
    ids = opts[0]["member_ids"]
    assert client.post("/api/find/accept", json={"member_ids": ids}, headers=hs[0]).status_code == 200
    c = client.get("/api/circle", headers=hs[0]).json()
    assert c["status"] == "proposed" and c["my_status"] == "accepted"
    assert all(m["phone"] is None for m in c["members"]), "numbers hidden until everyone accepts"
    # Others in the proposal are no longer offered to anyone else.
    h5 = student(client, 5)
    others = client.get("/api/find/options", headers=h5).json()["options"]
    assert not any(set(o["member_ids"]) & (set(ids) - {me(client, hs[0])["id"]}) for o in others)
    for h in hs[1:]:
        if me(client, h)["id"] in ids:
            client.post("/api/circle/respond", json={"accept": True}, headers=h)
    c = client.get("/api/circle", headers=hs[0]).json()
    assert c["status"] == "active" and all(m["phone"] for m in c["members"] if not m["me"])
    assert c["since"] == MONDAY.isoformat() and c["travel_days"]


def test_accept_rechecks_availability(client):
    a, _b, x = student(client, 1), student(client, 2), student(client, 3)
    opts_a = client.get("/api/find/options", headers=a).json()["options"]
    opts_x = client.get("/api/find/options", headers=x).json()["options"]
    client.post("/api/find/accept", json={"member_ids": opts_x[0]["member_ids"]}, headers=x)
    r = client.post("/api/find/accept", json={"member_ids": opts_a[0]["member_ids"]}, headers=a)
    assert r.status_code == 409  # a is now in x's proposal, so must answer that first
    assert client.get("/api/circle", headers=a).json()["status"] == "proposed"


def test_decline_remembered(client):
    a, b = student(client, 1), student(client, 2)
    opts = client.get("/api/find/options", headers=a).json()["options"]
    client.post("/api/find/accept", json={"member_ids": opts[0]["member_ids"]}, headers=a)
    client.post("/api/circle/respond", json={"accept": False}, headers=b)
    assert client.get("/api/circle", headers=a).json() is None
    assert client.get("/api/find/options", headers=a).json()["options"] == []


def test_women_only_never_matched_with_men(client):
    w = student(client, 1, women_only=True)
    student(client, 2, gender="male")
    student(client, 3, gender="male")
    assert client.get("/api/find/options", headers=w).json()["options"] == []


def test_today_check_in_fare_and_money(client):
    hs = [student(client, i) for i in range(1, 4)]
    circle_of(client, hs)
    t = client.get("/api/today", headers=hs[0]).json()
    assert t["trip"]["confirmed"] is False and t["trip"]["my_status"] == "planned"
    assert client.post("/api/today/yes", headers=hs[0]).status_code == 200
    t = client.get("/api/today", headers=hs[1]).json()
    assert t["trip"]["confirmed"] and t["trip"]["went"] == 3
    # Someone else says they didn't actually go.
    client.post("/api/today/correct", headers=hs[2])
    assert client.get("/api/today", headers=hs[2]).json()["trip"]["my_status"] == "notgoing"
    # Only the confirmer can enter the fare: Rs 150 each x 2 travellers.
    assert client.post("/api/today/fare", json={"share": 150}, headers=hs[1]).status_code == 403
    t = client.get("/api/today", headers=hs[0]).json()
    assert t["trip"]["ask_fare"] and len(t["trip"]["suggestions"]) == 3
    assert client.post("/api/today/fare", json={"share": 150}, headers=hs[0]).status_code == 200
    t = client.get("/api/today", headers=hs[1]).json()
    assert t["trip"]["share"] == 150 and t["trip"]["saved"] is not None
    m0 = client.get("/api/money", headers=hs[0]).json()
    m1 = client.get("/api/money", headers=hs[1]).json()
    assert m0["balance"] == 150 and m1["balance"] == -150
    assert m1["lines"][0]["amount"] == 150 and m1["lines"][0]["to"] != "You"
    line = m1["lines"][0]
    client.post("/api/money/settle", json={k: line[k] for k in ("from_id", "to_id", "amount")}, headers=hs[1])
    assert client.get("/api/money", headers=hs[0]).json()["balance"] == 0


def test_not_going_tomorrow(client):
    hs = [student(client, i) for i in range(1, 3)]
    circle_of(client, hs)
    t = client.get("/api/today", headers=hs[0]).json()
    assert t["tomorrow"]["planned"] and not t["tomorrow"]["off"]
    client.post("/api/tomorrow", json={"going": False}, headers=hs[0])
    assert client.get("/api/today", headers=hs[0]).json()["tomorrow"]["off"]
    clock.set_today(MONDAY + timedelta(days=1))
    t = client.get("/api/today", headers=hs[1]).json()
    statuses = {m["name"]: m["status"] for m in t["members"]}
    assert "planned" in statuses.values() and None in statuses.values()


def test_no_trip_on_weekend(client):
    hs = [student(client, i) for i in range(1, 3)]
    circle_of(client, hs)
    clock.set_today(MONDAY - timedelta(days=1))  # Sunday
    t = client.get("/api/today", headers=hs[0]).json()
    assert t["trip"] is None and t["tomorrow"]["date"] == MONDAY.isoformat()


def test_rota_fair_and_swappable(client):
    hs = [student(client, i, methods=(CD,), has_car=True, seats=3) for i in range(1, 3)]
    c = circle_of(client, hs)
    assert c["mode"] == CD and c["is_driver_mode"]
    counts = {}
    for e in c["rota"]:
        counts[e["user_id"]] = counts.get(e["user_id"], 0) + 1
    assert len(counts) == 2 and max(counts.values()) - min(counts.values()) <= 1
    first = c["rota"][0]
    mine = me(client, hs[0])["id"]
    h_driver = hs[0] if first["user_id"] == mine else hs[1]
    c2 = client.post("/api/circle/rota/cant", json={"day": first["day"]}, headers=h_driver).json()
    assert c2["rota"][0]["user_id"] != first["user_id"]
    c3 = client.post("/api/circle/rota/take", json={"day": first["day"]}, headers=h_driver).json()
    assert c3["rota"][0]["user_id"] == first["user_id"]


def test_change_mode_and_leave(client):
    hs = [student(client, i, methods=(SH, "Rickshaw")) for i in range(1, 4)]
    c = circle_of(client, hs)
    assert set(c["modes"]) == {SH, "Rickshaw"}
    assert client.patch("/api/circle/mode", json={"mode": "Rickshaw"}, headers=hs[1]).json()["mode"] == "Rickshaw"
    assert client.patch("/api/circle/mode", json={"mode": CD}, headers=hs[1]).status_code == 409
    client.post("/api/circle/leave", headers=hs[2])
    left = client.get("/api/circle", headers=hs[0]).json()
    assert left["status"] == "active" and len(left["members"]) == 2
    client.post("/api/circle/leave", headers=hs[1])
    assert client.get("/api/circle", headers=hs[0]).json() is None, "a circle of one ends"


def test_feedback_badges_and_noshow(client):
    hs = [student(client, i) for i in range(1, 4)]
    circle_of(client, hs)
    client.post("/api/today/yes", headers=hs[0])
    target = me(client, hs[1])["id"]
    assert client.post("/api/circle/feedback", json={"to_id": target, "up": True, "tag": "Punctual"},
                       headers=hs[0]).status_code == 201
    assert client.post("/api/circle/feedback", json={"to_id": target, "up": True, "tag": "Made up"},
                       headers=hs[0]).status_code == 422
    client.post("/api/circle/feedback", json={"to_id": target, "up": False, "tag": "Didn’t turn up"}, headers=hs[2])
    t = client.get("/api/today", headers=hs[1]).json()
    assert t["trip"]["my_status"] == "noshow"


def test_report_and_leave(client, admin):
    hs = [student(client, i) for i in range(1, 4)]
    circle_of(client, hs)
    target = me(client, hs[1])["id"]
    r = client.post("/api/circle/report", json={"reported_id": target, "reason": "Made me feel unsafe"}, headers=hs[0])
    assert r.status_code == 201
    assert client.get("/api/circle", headers=hs[0]).json() is None
    rep = client.get("/api/admin/reports", headers=admin).json()["reports"][0]
    assert rep["reason"] == "Made me feel unsafe" and rep["status"] == "open"


def test_one_day_seat(client):
    a = [student(client, i, area="Gulshan-e-Iqbal Block 13") for i in range(1, 3)]
    b = [student(client, i, area="Gulshan-e-Iqbal Block 10") for i in range(3, 5)]
    circle_of(client, a, n=2)
    circle_of(client, b, n=2)
    seats = client.get("/api/seats", headers=a[0]).json()
    assert seats and seats[0]["free"] >= 1
    assert client.post("/api/seats", json={"circle_id": seats[0]["circle_id"]}, headers=a[0]).status_code == 201
    req = client.get("/api/today", headers=b[0]).json()["seat_requests"][0]
    client.post(f"/api/seats/{req['id']}/answer", json={"accept": True}, headers=b[0])
    ta = client.get("/api/today", headers=a[0]).json()
    assert ta["guest"] and ta["trip"]["my_status"] == "notgoing"
    tb = client.get("/api/today", headers=b[0]).json()
    assert len(tb["members"]) == 2  # guest is on the trip but not a circle member
    client.post(f"/api/seats/{ta['guest']['seat_id']}/cancel", headers=a[0])
    assert client.get("/api/today", headers=a[0]).json()["trip"]["my_status"] == "planned"


def test_rematch_moves_student_to_new_circle(client):
    old = [student(client, i) for i in range(1, 3)]
    circle_of(client, old)
    new = student(client, 3)
    opts = client.get("/api/find/options", headers=old[0]).json()["options"]
    target = next(o for o in opts if me(client, new)["id"] in o["member_ids"])
    client.post("/api/find/accept", json={"member_ids": target["member_ids"]}, headers=old[0])
    for h in (old[1], new):
        if me(client, h)["id"] in target["member_ids"]:
            client.post("/api/circle/respond", json={"accept": True}, headers=h)
    c = client.get("/api/circle", headers=old[0]).json()
    assert c["status"] == "active" and me(client, new)["id"] in [m["user_id"] for m in c["members"]]


def test_savings(client):
    hs = [student(client, i) for i in range(1, 3)]
    circle_of(client, hs)
    client.post("/api/today/yes", headers=hs[0])
    client.post("/api/today/fare", json={"share": 200}, headers=hs[0])
    clock.set_today(MONDAY + timedelta(days=7))
    s = client.get("/api/savings", headers=hs[1]).json()
    assert s["tiles"]["went"] == 1 and s["tiles"]["paid"] == 200 and s["weeks"][-1]["paid"] == 200
    assert any(g["mode"] == SH and g["n"] == 2 and g["median"] == 200 for g in s["guide"])  # one share per traveller


def test_passenger_pays_modes_do_not_charge_the_provider(client):
    hs = [student(client, i, methods=("Family driver",)) for i in range(1, 4)]
    c = circle_of(client, hs)
    assert c["mode"] == "Family driver" and c["cost"]["payers"] == 2  # host family pays nothing
    t = client.get("/api/today", headers=hs[0]).json()["trip"]
    host = t["default_payer"]
    hh = next(h for h in hs if me(client, h)["id"] == host)
    client.post("/api/today/yes", headers=hh)
    client.post("/api/today/fare", json={"share": 100, "payer_id": host}, headers=hh)
    m = client.get("/api/money", headers=hh).json()
    assert m["balance"] == 200  # two passengers x Rs 100; the host isn't charged their own share
    others = [h for h in hs if h is not hh]
    assert all(client.get("/api/money", headers=h).json()["balance"] == -100 for h in others)


def test_sos_alerts_student_affairs(client, admin, monkeypatch):
    monkeypatch.setenv("CC_SECURITY_PHONE", "021-111-222-333")
    hs = [student(client, i) for i in range(1, 3)]
    circle_of(client, hs)
    client.patch("/api/auth/me", json={"emergency_name": "Ammi", "emergency_phone": "0333 7654321"}, headers=hs[0])
    r = client.post("/api/sos", json={"message": "Car broke down on Korangi Road"}, headers=hs[0]).json()
    assert [c["number"] for c in r["call"]] == ["15", "1122", "021-111-222-333"]
    sos = client.get("/api/admin/reports", headers=admin).json()["sos"][0]
    assert sos["handled"] is False and "BIC campus" in sos["route"] and sos["message"].startswith("Car")
    out = client.get("/api/admin/outbox", headers=admin).json()
    assert any(m["template"] == "cc_sos" and m["to"] == "+923337654321" and m["status"] == "mock" for m in out["messages"])
    client.patch(f"/api/admin/sos/{sos['id']}", json={"handled": True, "note": "Called the student"}, headers=admin)
    assert client.get("/api/admin/usage", headers=admin).json()["open_sos"] == 0


def test_ratings_build_bayesian_trust(client):
    from app.services.trips import trust_score

    assert trust_score([], 0, 0) == 4.0  # priors: 4.0 stars and 80 % reliability -> 4.0
    assert trust_score([5] * 20, 20, 0) > 4.7 and trust_score([2] * 10, 5, 5) < 3.0
    hs = [student(client, i) for i in range(1, 3)]
    circle_of(client, hs)
    other = me(client, hs[1])["id"]
    assert client.post("/api/today/rate", json={"ratings": [{"user_id": other, "stars": 5}]}, headers=hs[0]).status_code == 409
    client.post("/api/today/yes", headers=hs[0])
    assert client.post("/api/today/rate", json={"ratings": [{"user_id": other, "stars": 5}]}, headers=hs[0]).status_code == 201
    assert client.get("/api/today", headers=hs[0]).json()["trip"]["rated"] == {str(other): 5}
    m = next(x for x in client.get("/api/circle", headers=hs[0]).json()["members"] if x["user_id"] == other)
    assert m["ratings"] == 1 and m["trust"] > 4.0


def test_surveys_and_sus_scoring(client, admin):
    from app.services.surveys import sus_score

    assert sus_score([5, 1] * 5) == 100 and sus_score([1, 5] * 5) == 0 and sus_score([3] * 10) == 50
    hs = [student(client, i) for i in range(1, 3)]
    s = client.get("/api/surveys", headers=hs[0]).json()
    assert s["due"] == ["spend_before"] and len(s["sus_items"]) == 10
    assert client.post("/api/surveys/spend_before", json={"amount_pkr": 20000}, headers=hs[0]).status_code == 201
    assert client.post("/api/surveys/sus", json={"answers": [4, 2] * 5}, headers=hs[0]).status_code == 409  # needs 5 trips
    ev = {r["metric"]: r for r in client.get("/api/admin/evaluation", headers=admin).json()}
    assert ev["Matching success rate"]["target"] == ">= 75%" and ev["SUS usability score"]["value"] is None


def test_whatsapp_jobs_and_replies(client, admin, monkeypatch, db):
    import hashlib
    import hmac
    import json

    monkeypatch.setenv("CC_JOBS_TOKEN", "jobs-secret")
    monkeypatch.setenv("CC_WHATSAPP_APP_SECRET", "app-secret")
    monkeypatch.setenv("CC_WHATSAPP_VERIFY_TOKEN", "verify-me")
    hs = [student(client, i) for i in range(1, 3)]
    for h in hs:
        client.patch("/api/auth/me", json={"whatsapp_opt_in": True}, headers=h)
    circle_of(client, hs)
    assert client.post("/api/jobs/run", headers={"X-Jobs-Token": "nope"}).status_code == 403
    monkeypatch.setenv("CC_NOW", "2026-11-09T07:50")  # Monday, 40 min before the 08:30 arrival
    r = client.post("/api/jobs/run", headers={"X-Jobs-Token": "jobs-secret"}).json()
    assert r["reminders"] == 2
    assert client.post("/api/jobs/run", headers={"X-Jobs-Token": "jobs-secret"}).json()["reminders"] == 0  # once a day
    monkeypatch.setenv("CC_NOW", "2026-11-09T09:15")
    assert client.post("/api/jobs/run", headers={"X-Jobs-Token": "jobs-secret"}).json()["checkins"] == 2
    # Meta webhook verification and a signed "1" reply
    v = client.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"})
    assert v.text == "42"
    body = json.dumps({"entry": [{"changes": [{"value": {"messages": [{"from": "923001000001", "type": "text", "text": {"body": "1"}}]}}]}]}).encode()
    sig = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
    assert client.post("/api/whatsapp/webhook", content=body, headers={"X-Hub-Signature-256": "sha256=bad"}).status_code == 403
    assert client.post("/api/whatsapp/webhook", content=body, headers={"X-Hub-Signature-256": sig}).json()["handled"] == 1
    t = client.get("/api/today", headers=hs[0]).json()["trip"]
    assert t["confirmed"] and t["confirmed_by_me"]
    body2 = json.dumps({"entry": [{"changes": [{"value": {"messages": [{"from": "923001000001", "type": "text", "text": {"body": "150"}}]}}]}]}).encode()
    sig2 = "sha256=" + hmac.new(b"app-secret", body2, hashlib.sha256).hexdigest()
    client.post("/api/whatsapp/webhook", content=body2, headers={"X-Hub-Signature-256": sig2})
    assert client.get("/api/money", headers=hs[0]).json()["balance"] == 150
    out = client.get("/api/admin/outbox", headers=admin).json()["messages"]
    assert {m["template"] for m in out} >= {"cc_reminder", "cc_checkin", "cc_proposal", "text"}


def test_abuse_limits(client, admin):
    hs = [student(client, i, area="Gulshan-e-Iqbal Block 13") for i in range(1, 3)]
    others = [student(client, i, area="Gulshan-e-Iqbal Block 10") for i in range(3, 5)]
    third = [student(client, i, area="Gulshan-e-Iqbal Block 13") for i in range(5, 7)]
    circle_of(client, hs, n=2)
    circle_of(client, others, n=2)
    circle_of(client, third, n=2)
    target = me(client, hs[1])["id"]
    # Feedback: once a day per classmate.
    assert client.post("/api/circle/feedback", json={"to_id": target, "up": True, "tag": "Punctual"}, headers=hs[0]).status_code == 201
    assert client.post("/api/circle/feedback", json={"to_id": target, "up": False, "tag": "Rude"}, headers=hs[0]).status_code == 409
    # SOS pressed twice in a row is one alert.
    a1 = client.post("/api/sos", json={"message": "first"}, headers=hs[0]).json()["alert_id"]
    a2 = client.post("/api/sos", json={"message": "second"}, headers=hs[0]).json()["alert_id"]
    sos = client.get("/api/admin/reports", headers=admin).json()["sos"]
    assert a1 == a2 and len(sos) == 1 and sos[0]["message"] == "first | second"
    # One live seat request a day.
    seats = client.get("/api/seats", headers=hs[0]).json()
    assert len(seats) >= 2
    assert client.post("/api/seats", json={"circle_id": seats[0]["circle_id"]}, headers=hs[0]).status_code == 201
    assert client.post("/api/seats", json={"circle_id": seats[1]["circle_id"]}, headers=hs[0]).status_code == 409


def test_seat_offers_respect_vehicle_capacity(client):
    full = [student(client, i, methods=("Rickshaw",)) for i in range(1, 4)]  # a rickshaw carries 3
    c = circle_of(client, full)
    assert c["mode"] == "Rickshaw" and len(c["members"]) == 3
    lone = [student(client, i, area="Gulshan-e-Iqbal Block 10", methods=("Rickshaw",)) for i in range(4, 6)]
    circle_of(client, lone, n=2)
    seats = client.get("/api/seats", headers=lone[0]).json()
    assert all(s["circle_id"] != c["id"] for s in seats), "a full rickshaw must not offer a seat"
