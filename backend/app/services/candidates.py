from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..areas import area_coords
from ..config import settings
from ..matching.compat import Rules
from ..matching.types import Candidate
from ..models import CircleMember, CircleStatus, DeclinedPair, MemberStatus, Profile, User, Circle

LIVE_MEMBER = (MemberStatus.pending, MemberStatus.accepted)


def to_candidate(p: Profile) -> Candidate:
    return Candidate(
        user_id=p.user_id,
        location=area_coords(p.area),
        gender=p.gender.value,
        same_gender_only=p.same_gender_only,
        has_car=p.has_car,
        seats=p.seats if p.has_car else 0,
        schedule=p.schedule or {},
    )


def rules_for(db: Session) -> Rules:
    excluded = frozenset(
        frozenset((a, b)) for a, b in db.execute(select(DeclinedPair.user_id, DeclinedPair.other_id))
    )
    return Rules(
        campus=(settings.campus_lat, settings.campus_lng),
        window_min=settings.schedule_window_min,
        min_shared_days=settings.min_shared_days,
        max_circle_size=settings.max_circle_size,
        excluded=excluded,
    )


def busy_user_ids(db: Session) -> set[int]:
    """Students already in a proposed or active circle."""
    q = (
        select(CircleMember.user_id)
        .join(Circle)
        .where(Circle.status.in_([CircleStatus.proposed, CircleStatus.active]))
        .where(CircleMember.status.in_(LIVE_MEMBER))
    )
    return set(db.scalars(q))


def matching_pool(db: Session) -> list[Candidate]:
    busy = busy_user_ids(db)
    q = (
        select(Profile)
        .join(User)
        .where(Profile.seeking.is_(True), User.is_active.is_(True))
        .order_by(Profile.user_id)
    )
    return [to_candidate(p) for p in db.scalars(q) if p.user_id not in busy and p.schedule]
