"""Circle lifecycle: propose -> every member accepts -> active -> (leave/dissolve)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..matching.algorithms import ALGORITHMS
from ..matching.compat import feasible
from ..matching.evaluate import evaluate
from ..config import settings
from ..models import Circle, CircleMember, CircleStatus, DeclinedPair, MatchRun, MemberStatus
from . import rota
from .candidates import matching_pool, rules_for, to_candidate


class CircleError(Exception):
    pass


def run_matching(db: Session, algorithm: str, triggered_by: int | None, seed: int = 0) -> MatchRun:
    """Form new circles from students who are seeking and not already in one.

    Existing circles and every student's profile are left untouched.
    """
    if algorithm not in ALGORITHMS:
        raise CircleError(f"Unknown algorithm '{algorithm}'")
    pool = matching_pool(db)
    rules = rules_for(db)
    result = ALGORITHMS[algorithm](pool, rules, seed)
    for pc in result.circles:
        circle = Circle(algorithm=algorithm, score=pc.score, status=CircleStatus.proposed)
        circle.members = [
            CircleMember(user_id=uid, is_driver=uid in pc.driver_ids, status=MemberStatus.pending)
            for uid in pc.member_ids
        ]
        db.add(circle)
    metrics = evaluate(result, pool, rules, road_factor=settings.road_factor,
                       km_per_litre=settings.fuel_km_per_litre, fuel_price=settings.fuel_price_pkr)
    run = MatchRun(
        algorithm=algorithm, triggered_by=triggered_by, pool_size=len(pool),
        circles_created=len(result.circles), students_matched=metrics["matched"], metrics=metrics,
    )
    db.add(run)
    db.commit()
    return run


def _live(circle: Circle) -> list[CircleMember]:
    return [m for m in circle.members if m.status in (MemberStatus.pending, MemberStatus.accepted)]


def _still_feasible(db: Session, circle: Circle) -> bool:
    group = [to_candidate(m.user.profile) for m in _live(circle) if m.user.profile]
    return feasible(group, rules_for(db))


def _dissolve(db: Session, circle: Circle, reason: str) -> None:
    circle.status = CircleStatus.dissolved
    circle.dissolved_reason = reason
    rota.regenerate(db, circle)


def _settle(db: Session, circle: Circle) -> None:
    """After any membership change, activate, keep, or dissolve the circle."""
    if not _still_feasible(db, circle):
        _dissolve(db, circle, "Circle no longer viable after a member left or declined")
        return
    if all(m.status == MemberStatus.accepted for m in _live(circle)):
        circle.status = CircleStatus.active
    rota.regenerate(db, circle)


def membership(circle: Circle, user_id: int) -> CircleMember:
    for m in circle.members:
        if m.user_id == user_id:
            return m
    raise CircleError("You are not a member of this circle")


def respond(db: Session, circle: Circle, user_id: int, accept: bool) -> Circle:
    if circle.status != CircleStatus.proposed:
        raise CircleError("This circle is no longer awaiting responses")
    m = membership(circle, user_id)
    if m.status != MemberStatus.pending:
        raise CircleError("You have already responded")
    if accept:
        m.status = MemberStatus.accepted
    else:
        m.status = MemberStatus.declined
        for other in circle.members:
            if other.user_id != user_id:
                db.add(DeclinedPair(user_id=user_id, other_id=other.user_id))
    db.flush()
    _settle(db, circle)
    db.commit()
    return circle


def leave(db: Session, circle: Circle, user_id: int) -> Circle:
    if circle.status == CircleStatus.dissolved:
        raise CircleError("This circle has already been dissolved")
    m = membership(circle, user_id)
    if m.status not in (MemberStatus.pending, MemberStatus.accepted):
        raise CircleError("You are not an active member of this circle")
    m.status = MemberStatus.left
    db.flush()
    _settle(db, circle)
    db.commit()
    return circle


def dissolve(db: Session, circle: Circle, reason: str) -> Circle:
    if circle.status == CircleStatus.dissolved:
        raise CircleError("Already dissolved")
    _dissolve(db, circle, reason)
    db.commit()
    return circle


def refresh_after_profile_change(db: Session, user_id: int) -> str | None:
    """Re-check the student's live circle after they edit their profile.

    Returns a warning if the edit makes the circle unworkable; the circle is
    not dissolved automatically, so members can talk it through first.
    """
    for m in db.query(CircleMember).filter_by(user_id=user_id):
        c = m.circle
        if c.status == CircleStatus.active and m.status == MemberStatus.accepted:
            rota.regenerate(db, c)
            if not _still_feasible(db, c):
                return "Your new schedule or settings no longer fit your circle. Talk to your circle or leave it."
    return None
