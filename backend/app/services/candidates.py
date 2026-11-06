from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..areas import area_coords
from ..config import settings
from ..matching.compat import Rules
from ..matching.types import Candidate
from ..models import Circle, CircleMember, CircleStatus, DeclinedPair, MemberStatus, Profile, User, UserStatus

LIVE = (MemberStatus.pending, MemberStatus.accepted)


def to_candidate(p: Profile) -> Candidate:
    return Candidate(
        user_id=p.user_id, location=area_coords(p.area), gender=p.gender.value,
        women_only=p.women_only and p.gender.value == "female", methods=tuple(p.methods or ()),
        has_car=p.has_car, seats=p.seats if p.has_car else 0, schedule=p.schedule or {},
    )


def rules_for(db: Session) -> Rules:
    excluded = frozenset(frozenset((a, b)) for a, b in db.execute(select(DeclinedPair.user_id, DeclinedPair.other_id)))
    return Rules(campus=(settings.campus_lat, settings.campus_lng), window_min=settings.schedule_window_min,
                 max_circle_size=settings.max_circle_size, excluded=excluded)


def live_circles_of(db: Session, user_id: int) -> list[Circle]:
    q = (select(Circle).join(CircleMember)
         .where(CircleMember.user_id == user_id, CircleMember.status.in_(LIVE),
                Circle.status.in_([CircleStatus.proposed, CircleStatus.active])))
    return list(db.scalars(q).unique())


def active_circle_of(db: Session, user_id: int) -> Circle | None:
    return next((c for c in live_circles_of(db, user_id) if c.status == CircleStatus.active), None)


def busy_user_ids(db: Session) -> set[int]:
    q = (select(CircleMember.user_id).join(Circle)
         .where(Circle.status.in_([CircleStatus.proposed, CircleStatus.active]), CircleMember.status.in_(LIVE)))
    return set(db.scalars(q))


def approved_profiles(db: Session) -> list[Profile]:
    q = (select(Profile).join(User).where(User.status == UserStatus.approved, Profile.seeking.is_(True))
         .order_by(Profile.user_id))
    return [p for p in db.scalars(q) if p.area and p.schedule and p.methods]


def matching_pool(db: Session) -> list[Candidate]:
    """Approved, seeking students who are not in a proposed or active circle."""
    busy = busy_user_ids(db)
    return [to_candidate(p) for p in approved_profiles(db) if p.user_id not in busy]
