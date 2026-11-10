"""Student Affairs screens (prototype admin tabs) plus the research matching lab."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import hmac
import io
from statistics import median

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, contains_eager

from ..areas import AREAS, area_coords
from ..config import settings
from ..db import get_db
from ..deps import admin_user
from ..matching.algorithms import ALGORITHMS, EXACT
from ..matching.compat import DAYS, METHODS
from ..matching.evaluate import evaluate
from ..matching import roads
from ..models import (Circle, CircleStatus, Feedback, MatchRun, Notification, Profile, Report, ReportStatus, Role,
                      SosAlert, Trip, TripMember, TripStatus, User, UserStatus)
from ..schemas import ApprovalIn, DissolveIn, MatchIn, ReportUpdate, SosUpdate
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


def _trip_totals(db: Session, by_circle: bool = False):
    """(planned, completed, no-shows) over every trip except today's unconfirmed ones, in one query."""
    done = case(((TripMember.status == TripStatus.went) & Trip.confirmed_by.is_not(None), 1), else_=0)
    noshow = case((TripMember.status == TripStatus.noshow, 1), else_=0)
    cols = [func.count(), func.sum(done), func.sum(noshow)]
    q = select(*([Trip.circle_id] if by_circle else []), *cols).select_from(TripMember).join(Trip).where(
        ~((Trip.day == clock.today()) & Trip.confirmed_by.is_(None)))
    if by_circle:
        return {cid: (int(n or 0), int(d or 0), int(ns or 0)) for cid, n, d, ns in db.execute(q.group_by(Trip.circle_id))}
    n, d, ns = db.execute(q).one()
    return int(n or 0), int(d or 0), int(ns or 0)


def _count(db: Session, *where) -> int:
    return db.scalar(select(func.count()).where(*where)) or 0


@router.get("/usage")
def usage(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    everyone = _students(db)
    students = [u for u in everyone if u.status == UserStatus.approved]
    in_circle = _circle_ids_by_user(db)
    stats = trips.stats_for(db, students, money=False)
    active = {u.id for u in students if stats[u.id]["active"]}
    rated = [stats[u.id]["trust"] for u in students if stats[u.id]["went"] or stats[u.id]["ratings"]]
    women = [u for u in students if u.profile and u.profile.gender.value == "female" and u.profile.area]
    planned, done, _ns = _trip_totals(db)
    today = clock.today()
    days = clock.past_weekdays(20) + ([today] if today.weekday() < 5 else [])
    confirmed = Trip.confirmed_by.is_not(None)
    by_day = dict(db.execute(select(Trip.day, func.count()).where(Trip.day >= days[0], confirmed).group_by(Trip.day)).all())
    per_day = [{"day": d.isoformat(), "n": by_day.get(d, 0)} for d in days]
    n_circles = _count(db, Circle.status == CircleStatus.active)
    week = clock.past_weekdays(5)
    travelling = db.scalar(select(func.count(func.distinct(Trip.circle_id))).join(Circle).where(
        Circle.status == CircleStatus.active, Trip.day >= week[0], confirmed)) or 0
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
            "circles": n_circles, "circles_travelling": travelling,
            "without": sum(1 for u in students if u.id not in in_circle), "per_day": per_day, "areas": areas,
            "pending": sum(1 for u in everyone if u.status == UserStatus.pending),
            "avg_trust": round(sum(rated) / len(rated), 2) if rated else None,
            "trust_45": round(sum(t >= 4.5 for t in rated) / len(rated) * 100) if rated else None,
            "women_only_pct": round(sum(u.profile.women_only for u in women) / len(women) * 100) if women else None,
            "open_sos": _count(db, SosAlert.handled.is_(False)),
            "open_reports": _count(db, Report.status == ReportStatus.open)}


@router.get("/fares")
def fares(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    """Medians of fares entered in the last 90 days, by area and way of travelling."""
    grouped: dict[tuple[str, str], list[float]] = {}
    for area, mode, share in trips.fare_shares(db):
        grouped.setdefault((area, mode), []).append(share)
    rows = []
    for (a, md), v in grouped.items():
        if len(v) >= 3 and a in AREAS and trips.rate_for(md) > 0:
            km = roads.km(area_coords(a), CAMPUS(), settings.road_factor)
            rows.append({"area": a, "mode": md, "n": len(v), "median": round(median(v)), "road_km": round(km, 1),
                         "per_km": median(v) / km if km else 0})
    rows.sort(key=lambda r: (-r["median"], r["area"], r["mode"]))
    by_mode = []
    for md in METHODS:
        if trips.rate_for(md) <= 0:
            continue
        rr = [r for r in rows if r["mode"] == md]
        by_mode.append({"mode": md, "per_km": round(median([r["per_km"] for r in rr]), 1) if rr else None,
                        "n": sum(r["n"] for r in rr)})
    n_conf = _count(db, Trip.confirmed_by.is_not(None))
    with_fare = _count(db, Trip.confirmed_by.is_not(None), Trip.total > 0)
    return {"by_mode": by_mode, "fare_pct": round(with_fare / n_conf * 100) if n_conf else 0,
            "rows": [{k: v for k, v in r.items() if k != "per_km"} for r in rows]}


def _short(name: str) -> str:
    p = name.split()
    return f"{p[0]} {p[1][0]}." if len(p) > 1 else p[0]


@router.get("/health")
def health(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    circles = db.scalars(select(Circle).where(Circle.status == CircleStatus.active)).all()
    totals = _trip_totals(db, by_circle=True)
    members = [m.user for c in circles for m in c.members if m.status in LIVE]
    stats = trips.stats_for(db, members, money=False)
    neg_by = dict(db.execute(select(Feedback.to_id, func.count()).where(Feedback.up.is_(False)).group_by(Feedback.to_id)).all())
    start = clock.past_weekdays(trips.STREAK_WEEKDAYS)[0]
    conf_days: dict[int, set] = {}
    for cid, day in db.execute(select(Trip.circle_id, Trip.day).where(Trip.day >= start, Trip.confirmed_by.is_not(None))):
        conf_days.setdefault(cid, set()).add(day)
    rows = []
    for c in circles:
        live = [m for m in c.members if m.status in LIVE]
        pl, dn, ns = totals.get(c.id, (0, 0, 0))
        neg = sum(neg_by.get(m.user_id, 0) for m in live)
        rate = round(dn / pl * 100) if pl else 0
        trusts = [stats[m.user_id]["trust"] for m in live]
        rows.append({"circle_id": c.id, "members": [_short(m.user.full_name) for m in live],
                     "trust": round(sum(trusts) / len(trusts), 2) if trusts else None,
                     "areas": sorted({m.user.profile.area for m in live}), "mode": c.mode, "completed": rate,
                     "noshows": ns, "negative": neg, "streak": trips.streak(db, c, conf_days.get(c.id, set())),
                     "check_in": rate < 75 or ns >= 3 or neg >= 2 or (bool(trusts) and min(trusts) < 3.5)})
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
    if body.approve:
        u.approved_at = datetime.now(timezone.utc)
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
    sos = [{"id": a.id, "name": name(a.user_id), "phone": getattr(db.get(User, a.user_id), "phone", None) if a.user_id else None,
            "route": a.route, "message": a.message, "handled": a.handled, "note": a.handled_note, "created_at": a.created_at}
           for a in db.scalars(select(SosAlert).order_by(SosAlert.handled, SosAlert.id.desc()).limit(50))]
    return {"reports": reps, "negative_feedback": neg, "sos": sos}


@router.patch("/sos/{alert_id}")
def handle_sos(alert_id: int, body: SosUpdate, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    a = db.get(SosAlert, alert_id)
    if not a:
        raise HTTPException(404, "Alert not found")
    a.handled, a.handled_note = body.handled, body.note
    db.commit()
    return {"ok": True}


@router.get("/outbox")
def outbox(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    """Recent WhatsApp messages and emails; status "mock" means the service isn't configured yet."""
    from ..services import notify

    return {"whatsapp_ready": notify.whatsapp_ready(), "email_ready": notify.email_ready(),
            "messages": [{"id": n.id, "channel": n.channel, "to": n.to, "template": n.template, "body": n.body,
                          "status": n.status, "error": n.error, "created_at": n.created_at}
                         for n in db.scalars(select(Notification).order_by(Notification.id.desc()).limit(100))]}


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
    """Dry run: every algorithm on the current pool, plus the exact optimum when the pool is
    small enough to solve (MILP). Nothing is saved."""
    pool, r = matching_pool(db), rules_for(db)
    fns = dict(ALGORITHMS)
    if 2 <= len(pool) <= 90:
        fns.update(EXACT)
    out = []
    for fn in fns.values():
        try:
            res = fn(pool, r, seed)
        except ValueError:
            continue  # exact solver refused (too many circles to enumerate)
        out.append(evaluate(res, pool, r, road_factor=settings.road_factor, fuel_price=settings.fuel_price_pkr,
                            km_per_litre=settings.fuel_km_per_litre, speed_kmh=settings.avg_speed_kmh))
    return out


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
    w.writerow(["pid", "programme", "year", "area", "gender", "women_only", "methods", "has_car", "has_bike",
                "days_per_week", *[f"{d.lower()}_arrive" for d in DAYS], "in_active_circle", "circle_pid",
                "trips_travelled", "reliability_pct", "ratings_received", "trust_score"])
    q = (select(Profile).join(Profile.user).options(contains_eager(Profile.user))
         .where(User.research_consent.is_(True), User.status == UserStatus.approved))
    profiles = db.scalars(q.order_by(Profile.user_id)).all()
    stats = trips.stats_for(db, [p.user for p in profiles], money=False)
    for p in profiles:
        sched = p.schedule or {}
        cid = live.get(p.user_id)
        st = stats[p.user_id]
        w.writerow([_pseudonym("u", p.user_id), p.programme, p.year, p.area, p.gender.value, int(p.women_only),
                    "|".join(p.methods or []), int(p.has_car), int(bool(p.has_bike)), len(sched),
                    *[sched.get(d, {}).get("in", "") for d in DAYS], int(cid is not None),
                    _pseudonym("c", cid) if cid else "", st["went"], st["reliability"] if st["reliability"] is not None else "",
                    st["ratings"], st["trust"]])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=commutecircle-research.csv"})


@router.get("/evaluation")
def evaluation(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    """The proposal's targets (section 15 and RQ mapping) against live data."""
    import statistics as st

    from ..matching.compat import rider_detours_min
    from ..models import SurveyResponse
    from ..services.candidates import to_candidate

    students = [u for u in _students(db) if u.status == UserStatus.approved and u.profile and u.profile.area]
    in_circle = _circle_ids_by_user(db)
    women = [u for u in students if u.profile.gender.value == "female"]
    det = []
    active = db.scalars(select(Circle).where(Circle.status == CircleStatus.active)).all()
    for c in active:
        g = [to_candidate(m.user.profile) for m in c.members if m.status in LIVE and m.user.profile]
        if len(g) >= 2:
            det += list(rider_detours_min(g, CAMPUS(), settings.road_factor, settings.avg_speed_kmh).values())
    resp = {k: [r for r in db.scalars(select(SurveyResponse).where(SurveyResponse.kind == k))]
            for k in ("sus", "safety", "spend_before", "spend_after")}
    sus = [r.score for r in resp["sus"]]
    fem_ids = {u.id for u in women}
    safety_f = [r.score for r in resp["safety"] if r.user_id in fem_ids]
    before = {r.user_id: r.score for r in resp["spend_before"]}
    paired = [(before[r.user_id], r.score) for r in resp["spend_after"] if r.user_id in before and before[r.user_id] > 0]
    saving = [1 - a / b for b, a in paired]
    by_user = trips.stats_for(db, students)
    stats = [by_user[u.id] for u in students]
    rated = [s["trust"] for s in stats if s["went"] or s["ratings"]]
    est_saving = []
    for s in stats:
        if s["went"] and s["paid"] and s["saved"]:
            est_saving.append(s["saved"] / (s["saved"] + s["paid"]))
    lat = [(u.approved_at - u.created_at).total_seconds() / 3600 for u in _students(db)
           if u.approved_at and u.created_at and u.approved_at.tzinfo == u.created_at.tzinfo]
    incidents = len(db.scalars(select(SosAlert)).all()) + len(db.scalars(
        select(Report).where(Report.reason.in_(["Made me feel unsafe", "Inappropriate behaviour"]))).all())
    mean = lambda xs: round(st.mean(xs), 2) if xs else None  # noqa: E731
    pct = lambda xs: round(100 * st.mean(xs), 1) if xs else None  # noqa: E731
    rows = [
        ("Matching success rate", ">= 75%", pct([u.id in in_circle for u in students]), "%", "Approved students with trip answers who are in an active circle"),
        ("Mean rider detour", "<= 12 min", mean(det), "min", "Estimated from OSRM road times x traffic factor"),
        ("Riders within 12 min", "100%", pct([d <= 12 for d in det]), "%", "Hard rule in matching"),
        ("Commute cost reduction (survey)", ">= 40%", pct(saving), "%", f"Paired before/after spending, n = {len(saving)}"),
        ("Commute cost reduction (app estimate)", ">= 40%", pct(est_saving), "%", "Fare shares entered vs travelling alone"),
        ("Female students in a circle", ">= 85%", pct([u.id in in_circle for u in women]), "%", f"n = {len(women)}"),
        ("Women-only chosen by female students", "—", pct([u.profile.women_only for u in women]), "%", ""),
        ("SUS usability score", ">= 78", mean(sus), "/100", f"n = {len(sus)}"),
        ("Female safety perception", "—", mean(safety_f), "/5", f"n = {len(safety_f)}"),
        ("Safety incidents", "0", incidents, "", "SOS alerts + reports of unsafe or inappropriate behaviour"),
        ("Active circles", ">= 20", len(active), "", ""),
        ("Average trust score", ">= 4.5", mean(rated), "/5", f"n = {len(rated)}"),
        ("Admin verification latency", "<= 4 h", mean(lat), "h", f"Median {round(st.median(lat), 2) if lat else '—'} h, n = {len(lat)}"),
    ]
    return [{"metric": m, "target": t, "value": v, "unit": u, "note": n} for m, t, v, u, n in rows]
