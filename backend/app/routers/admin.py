"""Student Affairs screens (prototype admin tabs) plus the research matching lab."""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
from statistics import median

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..areas import AREAS, area_coords
from ..config import settings
from ..db import get_db
from ..deps import admin_user
from ..matching.algorithms import ALGORITHMS
from ..matching.compat import DAYS, METHODS
from ..matching.evaluate import evaluate
from ..matching.geo import haversine_km
from ..models import (Circle, CircleStatus, Feedback, MatchRun, Profile, Report, ReportStatus, Role, Trip, TripMember,
                      TripStatus, User, UserStatus)
from ..schemas import ApprovalIn, DissolveIn, MatchIn, ReportUpdate
from ..services import circles as svc
from ..services import clock, trips
from ..services.candidates import LIVE, matching_pool, rules_for
from .auth import user_out

router = APIRouter(prefix="/api/admin", tags=["admin"])
CAMPUS = lambda: (settings.campus_lat, settings.campus_lng)  # noqa: E731


def _students(db) -> list[User]:
    return list(db.scalars(select(User).where(User.role == Role.student).order_by(User.id)))


def _circle_ids_by_user(db) -> dict[int, int]:
    out = {}
    for c in db.scalars(select(Circle).where(Circle.status == CircleStatus.active)):
        for m in c.members:
            if m.status in LIVE:
                out[m.user_id] = c.id
    return out


@router.get("/usage")
def usage(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    students = [u for u in _students(db) if u.status == UserStatus.approved]
    in_circle = _circle_ids_by_user(db)
    active = {u.id for u in students if trips.user_stats(db, u)["active"]}
    planned = done = 0
    today = clock.today()
    for t in db.scalars(select(Trip)):
        if t.day == today and not t.confirmed_by:
            continue
        for m in t.members:
            planned += 1
            done += int(m.status == TripStatus.went and bool(t.confirmed_by))
    days = clock.past_weekdays(20) + ([today] if today.weekday() < 5 else [])
    per_day = [{"day": d.isoformat(), "n": len(db.scalars(select(Trip).where(Trip.day == d, Trip.confirmed_by.is_not(None))).all())}
               for d in days]
    circles = db.scalars(select(Circle).where(Circle.status == CircleStatus.active)).all()
    week = clock.past_weekdays(5)
    travelling = sum(1 for c in circles if db.scalar(select(Trip).where(Trip.circle_id == c.id, Trip.day >= week[0],
                                                                         Trip.confirmed_by.is_not(None))))
    areas = []
    for a in AREAS:
        ss = [u for u in students if u.profile and u.profile.area == a]
        if ss:
            ic = sum(1 for u in ss if u.id in in_circle)
            areas.append({"area": a, "coords": list(area_coords(a)), "members": len(ss), "in_circle": ic,
                          "active": sum(1 for u in ss if u.id in active), "without": len(ss) - ic})
    areas.sort(key=lambda r: (-r["without"], -r["members"]))
    return {"approved": len(students), "in_circle": sum(1 for u in students if u.id in in_circle),
            "active": len(active), "completion": round(done / planned * 100) if planned else 0,
            "circles": len(circles), "circles_travelling": travelling,
            "without": sum(1 for u in students if u.id not in in_circle), "per_day": per_day, "areas": areas,
            "pending": sum(1 for u in _students(db) if u.status == UserStatus.pending),
            "open_reports": len(db.scalars(select(Report).where(Report.status == ReportStatus.open)).all())}


@router.get("/fares")
def fares(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    rows = []
    for a in AREAS:
        for md in METHODS:
            if trips.rate_for(md) <= 0:
                continue
            v = trips.route_fares(db, a, md)
            if len(v) >= 3:
                km = haversine_km(area_coords(a), CAMPUS()) * settings.road_factor
                rows.append({"area": a, "mode": md, "n": len(v), "median": round(median(v)), "road_km": round(km, 1),
                             "per_km": median(v) / km if km else 0})
    rows.sort(key=lambda r: -r["median"])
    by_mode = []
    for md in METHODS:
        if trips.rate_for(md) <= 0:
            continue
        rr = [r for r in rows if r["mode"] == md]
        by_mode.append({"mode": md, "per_km": round(median([r["per_km"] for r in rr]), 1) if rr else None,
                        "n": sum(r["n"] for r in rr)})
    conf = db.scalars(select(Trip).where(Trip.confirmed_by.is_not(None))).all()
    with_fare = sum(1 for t in conf if t.total and t.total > 0)
    return {"by_mode": by_mode, "fare_pct": round(with_fare / len(conf) * 100) if conf else 0,
            "rows": [{k: v for k, v in r.items() if k != "per_km"} for r in rows]}


def _short(name: str) -> str:
    p = name.split()
    return f"{p[0]} {p[1][0]}." if len(p) > 1 else p[0]


@router.get("/health")
def health(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    today = clock.today()
    rows = []
    for c in db.scalars(select(Circle).where(Circle.status == CircleStatus.active)):
        live = [m for m in c.members if m.status in LIVE]
        pl = dn = ns = 0
        for t in db.scalars(select(Trip).where(Trip.circle_id == c.id)):
            if t.day == today and not t.confirmed_by:
                continue
            for m in t.members:
                pl += 1
                dn += int(m.status == TripStatus.went and bool(t.confirmed_by))
                ns += int(m.status == TripStatus.noshow)
        ids = [m.user_id for m in live]
        neg = len(db.scalars(select(Feedback).where(Feedback.up.is_(False), Feedback.to_id.in_(ids))).all())
        rate = round(dn / pl * 100) if pl else 0
        rows.append({"circle_id": c.id, "members": [_short(m.user.full_name) for m in live],
                     "areas": sorted({m.user.profile.area for m in live}), "mode": c.mode, "completed": rate,
                     "noshows": ns, "negative": neg, "streak": trips.streak(db, c),
                     "check_in": rate < 75 or ns >= 3 or neg >= 2})
    return sorted(rows, key=lambda r: r["completed"])


@router.get("/approvals")
def approvals(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    return [user_out(u) | {"area": u.profile.area if u.profile else None, "consent_version": u.consent_version,
                           "consented_at": u.consented_at, "created_at": u.created_at}
            for u in _students(db) if u.status == UserStatus.pending]


@router.post("/approvals/{user_id}")
def approve(user_id: int, body: ApprovalIn, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    u = db.get(User, user_id)
    if not u or u.status != UserStatus.pending:
        raise HTTPException(404, "No sign-up waiting with that id")
    u.status = UserStatus.approved if body.approve else UserStatus.rejected
    db.commit()
    return user_out(u)


@router.get("/reports")
def reports(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    name = lambda i: getattr(db.get(User, i), "full_name", "Deleted account") if i else "Deleted account"  # noqa: E731
    reps = [{"id": r.id, "reason": r.reason, "details": r.details, "status": r.status.value, "admin_note": r.admin_note,
             "from": name(r.reporter_id), "about": name(r.reported_id), "reported_id": r.reported_id,
             "circle_id": r.circle_id, "created_at": r.created_at}
            for r in db.scalars(select(Report).order_by(Report.status, Report.id.desc()))]
    neg = [{"about": name(f.to_id), "tag": f.tag, "from": name(f.from_id) if f.from_id else "Circle member",
            "created_at": f.created_at}
           for f in db.scalars(select(Feedback).where(Feedback.up.is_(False)).order_by(Feedback.id.desc()))]
    return {"reports": reps, "negative_feedback": neg}


@router.patch("/reports/{report_id}")
def update_report(report_id: int, body: ReportUpdate, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    r.status, r.admin_note = body.status, body.admin_note
    if body.status == ReportStatus.suspended and r.reported_id:
        _suspend(db, db.get(User, r.reported_id))
    db.commit()
    return {"ok": True}


def _suspend(db: Session, u: User) -> None:
    if u.role == Role.admin:
        raise HTTPException(422, "Admins cannot be suspended here")
    u.status = UserStatus.suspended
    svc.remove_user_everywhere(db, u)


@router.get("/users")
def users(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    return [user_out(u) | {"area": u.profile.area if u.profile else None} for u in db.scalars(select(User).order_by(User.id))]


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: dict, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    st = body.get("status")
    if st not in ("approved", "suspended"):
        raise HTTPException(422, "Status must be approved or suspended")
    if u.id == admin.id:
        raise HTTPException(422, "You cannot change your own account here")
    if st == "suspended":
        _suspend(db, u)
    else:
        u.status = UserStatus.approved
    db.commit()
    return user_out(u)


# --- Matching lab (research) -------------------------------------------------

@router.post("/compare")
def compare(seed: int = 0, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    """Dry run: every algorithm on the current pool; nothing is saved."""
    pool, r = matching_pool(db), rules_for(db)
    return [evaluate(fn(pool, r, seed), pool, r, road_factor=settings.road_factor, fuel_price=settings.fuel_price_pkr,
                     km_per_litre=settings.fuel_km_per_litre) for fn in ALGORITHMS.values()]


@router.post("/match")
def match(body: MatchIn, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    try:
        run = svc.run_matching(db, body.algorithm, admin.id, body.seed)
    except svc.CircleError as e:
        raise HTTPException(422, str(e)) from e
    return _run_out(run)


def _run_out(r: MatchRun) -> dict:
    return {"id": r.id, "algorithm": r.algorithm, "pool_size": r.pool_size, "circles_created": r.circles_created,
            "students_matched": r.students_matched, "metrics": r.metrics, "created_at": r.created_at}


@router.get("/runs")
def runs(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    return [_run_out(r) for r in db.scalars(select(MatchRun).order_by(MatchRun.id.desc()).limit(50))]


@router.get("/circles")
def circles(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    return [{"id": c.id, "status": c.status.value, "mode": c.mode, "fit": c.fit, "source": c.source,
             "since": c.since, "dissolved_reason": c.dissolved_reason,
             "members": [{"user_id": m.user_id, "name": m.user.full_name, "area": m.user.profile.area,
                          "status": m.status.value} for m in c.members]}
            for c in db.scalars(select(Circle).order_by(Circle.id.desc()))]


@router.post("/circles/{circle_id}/dissolve")
def dissolve(circle_id: int, body: DissolveIn, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    c = db.get(Circle, circle_id)
    if not c:
        raise HTTPException(404, "Circle not found")
    try:
        svc.dissolve(db, c, body.reason)
    except svc.CircleError as e:
        raise HTTPException(409, str(e)) from e
    return {"ok": True}


def _pseudonym(kind: str, i: int) -> str:
    return hmac.new(settings.secret_key.encode(), f"{kind}:{i}".encode(), hashlib.sha256).hexdigest()[:10]


@router.get("/research-export")
def research_export(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    """Pseudonymised CSV of students who opted in to research use. No names, emails or phones."""
    live = _circle_ids_by_user(db)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["pid", "programme", "year", "area", "gender", "women_only", "methods", "has_car", "days_per_week",
                *[f"{d.lower()}_arrive" for d in DAYS], "in_active_circle", "circle_pid", "trips_travelled",
                "reliability_pct"])
    q = select(Profile).join(User).where(User.research_consent.is_(True), User.status == UserStatus.approved)
    for p in db.scalars(q.order_by(Profile.user_id)):
        sched = p.schedule or {}
        cid = live.get(p.user_id)
        st = trips.user_stats(db, p.user)
        w.writerow([_pseudonym("u", p.user_id), p.programme, p.year, p.area, p.gender.value, int(p.women_only),
                    "|".join(p.methods or []), int(p.has_car), len(sched),
                    *[sched.get(d, {}).get("in", "") for d in DAYS], int(cid is not None),
                    _pseudonym("c", cid) if cid else "", st["went"], st["reliability"] if st["reliability"] is not None else ""])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=commutecircle-research.csv"})
