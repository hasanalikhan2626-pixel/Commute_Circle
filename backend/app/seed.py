"""Development / demo data.

    python -m app.seed             # the prototype's 71 students, circles and 4 weeks of trips
    python -m app.seed --empty     # admin only

Logins: admin@bic.edu.pk / admin12345, and every student <first>.<last>@bic.edu.pk /
student123 (e.g. ayesha.khan@bic.edu.pk). All data is fictional.
Refuses to run when CC_ENV=production.
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from .areas import AREAS
from .config import settings
from .db import Base, SessionLocal, engine
from .matching.algorithms import build_for
from .matching.compat import DAYS, METHODS, travel_modes, circle_fit
from .models import (Circle, CircleMember, CircleStatus, Feedback, Gender, MemberStatus, Profile, Report, Role,
                     Trip, TripMember, TripStatus, User, UserStatus)
from .security import hash_password
from .services import clock, rota, trips
from .services.candidates import rules_for, to_candidate

DEMO = json.loads((Path(__file__).parent / "demo_students.json").read_text())
NO_SEED = {15, 30, 34, 16, 20, 44, 43, 66, 6}  # left without a circle so "Find my circle" can be tried


def email_for(name: str) -> str:
    return name.lower().replace(" ", ".") + "@bic.edu.pk"


def _profile(s: dict) -> Profile:
    car = "Classmate drives" in s["methods"] and s["year"] >= 2
    return Profile(programme=s["programme"], year=s["year"], gender=Gender(s["gender"]), area=s["area"],
                   women_only=s["women_only"], methods=s["methods"], has_car=car, seats=3 if car else 0,
                   schedule=s["schedule"], seeking=True)


def seed(empty: bool = False, weeks: int = 4, rng_seed: int = 20261103) -> None:
    if settings.production:
        raise SystemExit("Refusing to seed: CC_ENV=production would wipe real student data.")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    rng = random.Random(rng_seed)
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        db.add(User(email="admin@bic.edu.pk", full_name="Student Affairs", role=Role.admin,
                    status=UserStatus.approved, password_hash=hash_password("admin12345")))
        if empty:
            db.commit()
            return
        pw = hash_password("student123")
        users = {}
        for s in DEMO:
            u = User(email=email_for(s["name"]), full_name=s["name"], password_hash=pw,
                     phone=f"+92300555{1000 + s['id']:04d}"[-13:], status=UserStatus(s["status"]),
                     consented_at=now, consent_version=settings.consent_version, research_consent=True)
            u.profile = _profile(s)
            db.add(u)
            users[s["id"]] = u
        db.flush()

        # Circles, formed the way the prototype seeds them.
        past = clock.past_weekdays(weeks * 5)
        rules = rules_for(db)
        avail = [to_candidate(users[s["id"]].profile) for s in DEMO
                 if s["status"] == "approved" and s["id"] not in NO_SEED]
        placed: set[int] = set()
        by_uid = {u.id: u for u in users.values()}
        circles = []
        for cand in sorted(avail, key=lambda c: c.user_id):
            if cand.user_id in placed:
                continue
            g = build_for(cand, [c for c in avail if c.user_id not in placed], rules)
            if not g:
                continue
            placed.update(c.user_id for c in g)
            c = Circle(mode=travel_modes(g)[0], fit=circle_fit(g, rules.campus), source="student",
                       status=CircleStatus.active, since=past[0], created_by=g[0].user_id)
            c.members = [CircleMember(user_id=x.user_id, position=n, status=MemberStatus.accepted)
                         for n, x in enumerate(g)]
            db.add(c)
            circles.append(c)
        db.flush()

        # Four weeks of trips with realistic no-shows, fares and feedback.
        for c in circles:
            members = [by_uid[m.user_id] for m in c.members]
            flaky = members[1 + rng.randrange(len(members) - 1)] if rng.random() < 0.25 else None
            for d in past:
                dn = clock.day_name(d)
                planned = [u for u in trips.plans_on(c, dn)] if dn in trips.travel_days(c) else []
                if len(planned) < 2:
                    continue
                t = Trip(circle_id=c.id, day=d, mode=c.mode)
                for u in planned:
                    r, ns = rng.random(), (0.22 if u is flaky else 0.04)
                    st = TripStatus.noshow if r < ns else TripStatus.notgoing if r < ns + 0.08 else TripStatus.went
                    t.members.append(TripMember(user_id=u.id, status=st))
                went = [m for m in t.members if m.status == TripStatus.went]
                if not went:
                    continue
                if rng.random() < 0.93:
                    t.confirmed_by = went[rng.randrange(len(went))].user_id
                    rate = trips.rate_for(c.mode)
                    if rate and rng.random() < 0.62:
                        km = trips.circle_route(c)["road_km"]
                        t.total = round(km * rate * (0.85 + rng.random() * 0.3) / 10) * 10
                        t.payer_id = t.confirmed_by if rng.random() < 0.6 else went[rng.randrange(len(went))].user_id
                db.add(t)
            c.settled_until = past[-6]
        db.flush()
        tags = trips.TAGS
        for c in circles:
            for m in c.members:
                for _ in range(rng.randrange(6)):
                    db.add(Feedback(to_id=m.user_id, circle_id=c.id, up=True, tag=tags[rng.randrange(len(tags))]))
        noshows = db.query(TripMember).filter(TripMember.status == TripStatus.noshow).limit(4).all()
        for tm in noshows:
            db.add(Feedback(to_id=tm.user_id, up=False, tag="Didn’t turn up", circle_id=tm.trip.circle_id))
        taha = db.query(User).filter_by(full_name="Taha Rizvi").one()
        kashif = db.query(User).filter_by(full_name="Kashif Noor").one()
        db.add(Report(reporter_id=taha.id, reported_id=kashif.id, reason="Repeatedly no-show",
                      details="Marked going three times last week but did not turn up."))
        for c in circles:
            rota.regenerate(db, c)
        db.commit()
    print(f"Seeded {len(DEMO)} prototype students in {len(circles)} circles.\n"
          "  admin@bic.edu.pk / admin12345\n  ayesha.khan@bic.edu.pk (and others) / student123")


def seed_if_empty() -> None:
    """For a demo deployment with no shell: CC_SEED_DEMO=true loads the demo data once,
    only into an empty database, and never when CC_ENV=production."""
    import os

    if os.environ.get("CC_SEED_DEMO", "").lower() not in ("1", "true", "yes") or settings.production:
        return
    with SessionLocal() as db:
        if db.query(User).count():
            return
    seed()


def make_students(n: int, seed: int = 42) -> list[dict]:
    """Random synthetic students in the prototype's style (benchmark only)."""
    rng = random.Random(seed)
    popular = ["Gulshan-e-Iqbal Block 13", "Gulshan-e-Iqbal Block 10", "Gulistan-e-Johar Block 15", "DHA Phase 6",
               "DHA Phase 8", "Defence View", "Korangi No. 5", "Mehmoodabad", "Shah Faisal Colony", "PECHS Block 6",
               "Bahadurabad", "Clifton Block 5"]
    plans = [("MTWHF", "08:30", "14:00"), ("MWF", "08:30", "14:00"), ("MTWH", "10:00", "16:00"),
             ("TH", "11:30", "17:00"), ("MTW", "08:45", "13:30")]
    dm = dict(zip("MTWHF", DAYS))
    out = []
    for i in range(1, n + 1):
        g = "female" if rng.random() < 0.5 else "male"
        area = rng.choice(popular) if rng.random() < 0.8 else rng.choice(sorted(AREAS))
        days, arr, lv = rng.choice(plans)
        h, m = map(int, arr.split(":"))
        t = h * 60 + m + rng.choice([-10, -5, 0, 0, 5, 10])
        arr = f"{t // 60:02d}:{t % 60:02d}"
        methods = rng.sample(METHODS, rng.choice([1, 1, 2, 2, 3]))
        if rng.random() < 0.6 and "Shared ride-hailing" not in methods:
            methods.append("Shared ride-hailing")
        car = "Classmate drives" in methods and rng.random() < 0.5
        bike = "Motorbike pillion" in methods and g == "male" and rng.random() < 0.6
        out.append(dict(user_id=i, gender=g, area=area, women_only=g == "female" and rng.random() < 0.5,
                        methods=methods, has_car=car, seats=3 if car else 0, has_bike=bike,
                        schedule={dm[c]: {"in": arr, "out": lv} for c in days}))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--empty", action="store_true")
    seed(ap.parse_args().empty)
