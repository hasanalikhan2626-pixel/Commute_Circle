from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import current_user
from ..matching.compat import group_days
from ..models import Circle, CircleMember, CircleStatus, DriverUnavailability, MemberStatus, Report, Role, User
from ..schemas import CircleOut, MemberOut, ReportIn, RespondIn, RotaOut, UnavailableIn
from ..services import circles as svc
from ..services import rota
from ..services.candidates import to_candidate
from ..services.costs import circle_costs

router = APIRouter(prefix="/api", tags=["circles"])


def circle_out(db: Session, c: Circle, viewer: User) -> CircleOut:
    live = [m for m in c.members if m.status in (MemberStatus.pending, MemberStatus.accepted)]
    profiles = [m.user.profile for m in live if m.user.profile]
    names = {m.user_id: m.user.full_name for m in c.members}
    reveal = c.status == CircleStatus.active or viewer.role == Role.admin
    me = next((m for m in c.members if m.user_id == viewer.id), None)
    members = [
        MemberOut(
            user_id=m.user_id, full_name=m.user.full_name,
            area=m.user.profile.area if m.user.profile else None,
            is_driver=m.is_driver, status=m.status,
            phone=m.user.phone if reveal and m in live else None,
            pickup_landmark=m.user.profile.pickup_landmark if reveal and m in live and m.user.profile else None,
        )
        for m in c.members
        if m in live or viewer.role == Role.admin
    ]
    days = group_days([to_candidate(p) for p in profiles], settings.schedule_window_min) if profiles else []
    today = date.today()
    return CircleOut(
        id=c.id, status=c.status, algorithm=c.algorithm, score=c.score, created_at=c.created_at,
        dissolved_reason=c.dissolved_reason, shared_days=days, members=members,
        rota=[RotaOut(day=e.day, driver_id=e.driver_id, driver_name=names.get(e.driver_id), arrive=e.arrive)
              for e in c.rota if e.day >= today],
        costs=circle_costs(db, profiles) if c.status != CircleStatus.dissolved else {"available": False},
        my_status=me.status if me else None,
    )


def load_circle(db: Session, circle_id: int, user: User) -> Circle:
    c = db.get(Circle, circle_id)
    if not c:
        raise HTTPException(404, "Circle not found")
    if user.role != Role.admin and not any(m.user_id == user.id for m in c.members):
        raise HTTPException(404, "Circle not found")
    return c


def _svc(fn, *args):
    try:
        return fn(*args)
    except svc.CircleError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/circles/mine", response_model=list[CircleOut])
def my_circles(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The student's circles, live ones first, then history (most recent first)."""
    q = select(Circle).join(CircleMember).where(CircleMember.user_id == user.id).order_by(Circle.created_at.desc())
    circles = db.scalars(q).unique().all()
    order = {CircleStatus.proposed: 0, CircleStatus.active: 0, CircleStatus.dissolved: 1}
    circles = sorted(circles, key=lambda c: order[c.status])
    return [circle_out(db, c, user) for c in circles]


@router.get("/circles/{circle_id}", response_model=CircleOut)
def get_circle(circle_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return circle_out(db, load_circle(db, circle_id, user), user)


@router.post("/circles/{circle_id}/respond", response_model=CircleOut)
def respond(circle_id: int, body: RespondIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = _svc(svc.respond, db, load_circle(db, circle_id, user), user.id, body.accept)
    return circle_out(db, c, user)


@router.post("/circles/{circle_id}/leave", response_model=CircleOut)
def leave(circle_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = _svc(svc.leave, db, load_circle(db, circle_id, user), user.id)
    return circle_out(db, c, user)


@router.post("/circles/{circle_id}/unavailable", response_model=CircleOut)
def mark_unavailable(circle_id: int, body: UnavailableIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    c = load_circle(db, circle_id, user)
    m = _svc(svc.membership, c, user.id)
    if c.status != CircleStatus.active or not m.is_driver:
        raise HTTPException(409, "Only drivers in an active circle can mark days unavailable")
    if body.day < date.today():
        raise HTTPException(422, "That day has already passed")
    exists = db.scalar(select(DriverUnavailability).filter_by(circle_id=c.id, user_id=user.id, day=body.day))
    if not exists:
        db.add(DriverUnavailability(circle_id=c.id, user_id=user.id, day=body.day))
        db.flush()
    rota.regenerate(db, c)
    db.commit()
    return circle_out(db, c, user)


@router.delete("/circles/{circle_id}/unavailable/{day}", response_model=CircleOut)
def clear_unavailable(circle_id: int, day: date, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = load_circle(db, circle_id, user)
    row = db.scalar(select(DriverUnavailability).filter_by(circle_id=c.id, user_id=user.id, day=day))
    if row:
        db.delete(row)
        db.flush()
        rota.regenerate(db, c)
        db.commit()
    return circle_out(db, c, user)


@router.post("/reports", status_code=201)
def create_report(body: ReportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.reported_id == user.id:
        raise HTTPException(422, "You cannot report yourself")
    # Students may only report people they have shared a circle with.
    mine = set(db.scalars(select(CircleMember.circle_id).where(CircleMember.user_id == user.id)))
    theirs = set(db.scalars(select(CircleMember.circle_id).where(CircleMember.user_id == body.reported_id)))
    if not mine & theirs:
        raise HTTPException(403, "You can only report members of your circles")
    db.add(Report(reporter_id=user.id, **body.model_dump()))
    db.commit()
    return {"ok": True}
