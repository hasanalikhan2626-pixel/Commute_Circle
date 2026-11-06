from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import admin_user
from ..matching.algorithms import ALGORITHMS
from ..matching.evaluate import evaluate
from ..config import settings
from ..models import Circle, CircleMember, CircleStatus, MatchRun, MemberStatus, Profile, Report, ReportStatus, User
from ..schemas import AdminUserUpdate, CircleOut, DissolveIn, MatchIn, MatchRunOut, ReportOut, ReportUpdate, UserOut
from ..services import circles as svc
from ..services.candidates import matching_pool, rules_for
from .auth import user_out
from .circles import circle_out

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def stats(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    count = lambda q: db.scalar(select(func.count()).select_from(q.subquery()))  # noqa: E731
    by_status = dict(db.execute(select(Circle.status, func.count()).group_by(Circle.status)).all())
    in_active = count(select(CircleMember.user_id).join(Circle)
                      .where(Circle.status == CircleStatus.active, CircleMember.status == MemberStatus.accepted))
    profiles = count(select(Profile.user_id))
    last = db.scalar(select(MatchRun).order_by(MatchRun.id.desc()))
    return {
        "students": count(select(User.id).where(User.role == "student")),
        "profiles": profiles,
        "drivers": count(select(Profile.user_id).where(Profile.has_car.is_(True))),
        "seeking_unmatched": len(matching_pool(db)),
        "circles": {s.value: by_status.get(s, 0) for s in CircleStatus},
        "students_in_active_circles": in_active,
        "active_match_rate": round(in_active / profiles, 3) if profiles else 0.0,
        "open_reports": count(select(Report.id).where(Report.status == ReportStatus.open)),
        "last_run": MatchRunOut.model_validate(last).model_dump() if last else None,
    }


@router.post("/match", response_model=MatchRunOut)
def match(body: MatchIn, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    try:
        return svc.run_matching(db, body.algorithm, admin.id, body.seed)
    except svc.CircleError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/compare")
def compare(seed: int = 0, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    """Dry run: evaluate every algorithm on the current pool without saving anything."""
    pool, rules = matching_pool(db), rules_for(db)
    return [
        evaluate(fn(pool, rules, seed), pool, rules, road_factor=settings.road_factor,
                 km_per_litre=settings.fuel_km_per_litre, fuel_price=settings.fuel_price_pkr)
        for fn in ALGORITHMS.values()
    ]


@router.get("/runs", response_model=list[MatchRunOut])
def runs(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    return db.scalars(select(MatchRun).order_by(MatchRun.id.desc()).limit(50)).all()


@router.get("/circles", response_model=list[CircleOut])
def all_circles(status: CircleStatus | None = None, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    q = select(Circle).order_by(Circle.id.desc())
    if status:
        q = q.where(Circle.status == status)
    return [circle_out(db, c, admin) for c in db.scalars(q)]


@router.post("/circles/{circle_id}/dissolve", response_model=CircleOut)
def dissolve(circle_id: int, body: DissolveIn, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    c = db.get(Circle, circle_id)
    if not c:
        raise HTTPException(404, "Circle not found")
    try:
        svc.dissolve(db, c, body.reason)
    except svc.CircleError as e:
        raise HTTPException(409, str(e)) from e
    return circle_out(db, c, admin)


@router.get("/reports", response_model=list[ReportOut])
def reports(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    out = []
    for r in db.scalars(select(Report).order_by(Report.status, Report.id.desc())):
        o = ReportOut.model_validate(r)
        o.reporter_name = getattr(db.get(User, r.reporter_id), "full_name", None)
        o.reported_name = getattr(db.get(User, r.reported_id), "full_name", None)
        out.append(o)
    return out


@router.patch("/reports/{report_id}", response_model=ReportOut)
def update_report(report_id: int, body: ReportUpdate, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    r.status, r.admin_note = body.status, body.admin_note
    db.commit()
    return ReportOut.model_validate(r)


@router.get("/users", response_model=list[UserOut])
def users(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    return [user_out(u) for u in db.scalars(select(User).order_by(User.id))]


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: AdminUserUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(422, "You cannot suspend yourself")
    u.is_active = body.is_active
    if not body.is_active:
        # A suspended student is removed from any live circle immediately.
        for m in list(u.memberships):
            if m.status in (MemberStatus.pending, MemberStatus.accepted) and m.circle.status != CircleStatus.dissolved:
                svc.leave(db, m.circle, u.id)
    db.commit()
    return user_out(u)
