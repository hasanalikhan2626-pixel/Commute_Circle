"""Circle lifecycle: a student picks an option -> everyone else accepts -> active.

Students start matching themselves ("Find my circle"). The admin batch run (research)
creates circles the same way, with every member pending.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..config import settings
from ..matching.algorithms import ALGORITHMS, options_for
from ..matching.compat import circle_fit, feasible, travel_modes
from ..matching.evaluate import evaluate
from ..models import (Circle, CircleMember, CircleStatus, DeclinedPair, MatchRun, MemberStatus, Profile, User,
                      UserStatus)
from . import clock, rota
from .candidates import LIVE, live_circles_of, matching_pool, rules_for, to_candidate

PROPOSAL_DAYS = 3  # a proposal nobody finishes answering is withdrawn after this


class CircleError(Exception):
    pass


def live_members(c: Circle) -> list[CircleMember]:
    return [m for m in c.members if m.status in LIVE]


def group_of(c: Circle):
    return [to_candidate(m.user.profile) for m in live_members(c) if m.user.profile]


# --- finding a circle --------------------------------------------------------

def _seeker(db: Session, user: User):
    if user.status != UserStatus.approved:
        raise CircleError("Your sign-up is waiting for approval by Student Affairs")
    from . import notify

    if notify.email_ready() and not user.email_verified:
        raise CircleError("Verify your email first: enter the 6-digit code we emailed you")
    if not user.profile or not user.profile.schedule or not user.profile.methods:
        raise CircleError("Answer the three trip questions first")
    return to_candidate(user.profile)


def find_pool(db: Session, user: User):
    """Classmates the student could be matched with: everyone free, plus (when re-matching)
    the members of the student's own current circle."""
    pool = {c.user_id: c for c in matching_pool(db)}
    for circ in live_circles_of(db, user.id):
        if circ.status == CircleStatus.proposed:
            raise CircleError("You already have a circle waiting for answers")
        for m in live_members(circ):
            if m.user.profile and m.user.status == UserStatus.approved:
                pool[m.user_id] = to_candidate(m.user.profile)
    pool[user.id] = _seeker(db, user)
    return list(pool.values())


def find_options(db: Session, user: User) -> list[list]:
    me = _seeker(db, user)
    pool = find_pool(db, user)
    return options_for(me, pool, rules_for(db))


def accept_option(db: Session, user: User, member_ids: list[int]) -> Circle:
    """Propose the chosen circle. Re-checked now, because classmates may have been matched since."""
    pool = {c.user_id: c for c in find_pool(db, user)}
    ids = [user.id] + [i for i in dict.fromkeys(member_ids) if i != user.id]
    if any(i not in pool for i in ids):
        raise CircleError("Someone in this circle has just been matched. Search again for fresh options.")
    group = [pool[i] for i in ids]
    rules = rules_for(db)
    if not feasible(group, rules):
        raise CircleError("This circle no longer works. Search again for fresh options.")
    circle = Circle(mode=travel_modes(group)[0], fit=circle_fit(group, rules.campus), source="student",
                    created_by=user.id, status=CircleStatus.proposed)
    circle.members = [CircleMember(user_id=i, position=n, status=MemberStatus.accepted if i == user.id
                                   else MemberStatus.pending) for n, i in enumerate(ids)]
    db.add(circle)
    db.flush()
    from .jobs import notify_proposal

    notify_proposal(db, circle)
    db.commit()
    return circle


def run_matching(db: Session, algorithm: str, triggered_by: int | None, seed: int = 0) -> MatchRun:
    """Admin batch run (research). Existing circles and profiles are never changed."""
    if algorithm not in ALGORITHMS:
        raise CircleError(f"Unknown algorithm '{algorithm}'")
    pool, rules = matching_pool(db), rules_for(db)
    result = ALGORITHMS[algorithm](pool, rules, seed)
    for pc in result.circles:
        c = Circle(mode=pc.mode, fit=pc.fit, source=algorithm, status=CircleStatus.proposed, created_by=triggered_by)
        c.members = [CircleMember(user_id=u, position=n) for n, u in enumerate(pc.member_ids)]
        db.add(c)
    metrics = evaluate(result, pool, rules, road_factor=settings.road_factor, fuel_price=settings.fuel_price_pkr,
                       km_per_litre=settings.fuel_km_per_litre, speed_kmh=settings.avg_speed_kmh)
    run = MatchRun(algorithm=algorithm, triggered_by=triggered_by, pool_size=len(pool),
                   circles_created=len(result.circles), students_matched=metrics["matched"], metrics=metrics)
    db.add(run)
    db.commit()
    return run


# --- membership changes -----------------------------------------------------

def membership(c: Circle, user_id: int) -> CircleMember:
    for m in c.members:
        if m.user_id == user_id:
            return m
    raise CircleError("You are not a member of this circle")


def _dissolve(db: Session, c: Circle, reason: str) -> None:
    c.status = CircleStatus.dissolved
    c.dissolved_reason = reason
    rota.regenerate(db, c)


def _activate(db: Session, c: Circle) -> None:
    c.status = CircleStatus.active
    c.since = clock.today()
    db.flush()
    # Re-matching: joining this circle means leaving any other one.
    for m in live_members(c):
        for other in live_circles_of(db, m.user_id):
            if other.id != c.id:
                om = membership(other, m.user_id)
                om.status = MemberStatus.left
                db.flush()
                _settle(db, other, activating=False)
    rota.regenerate(db, c)


def _settle(db: Session, c: Circle, activating: bool = True) -> None:
    """After any membership change: keep, activate or dissolve the circle."""
    group = group_of(c)
    modes = travel_modes(group) if len(group) >= 2 else []
    if len(group) < 2 or not modes:
        _dissolve(db, c, "Not enough members left to travel together")
        return
    if c.mode not in modes:
        c.mode = modes[0]
    if c.status == CircleStatus.proposed:
        if all(m.status == MemberStatus.accepted for m in live_members(c)) and activating:
            _activate(db, c)
    else:
        rota.regenerate(db, c)


def respond(db: Session, c: Circle, user_id: int, accept: bool) -> Circle:
    expire_if_stale(db, c)
    if c.status != CircleStatus.proposed:
        raise CircleError("This circle is no longer waiting for answers")
    m = membership(c, user_id)
    if m.status != MemberStatus.pending:
        raise CircleError("You have already answered")
    if accept:
        m.status = MemberStatus.accepted
    else:
        m.status = MemberStatus.declined
        for other in c.members:
            if other.user_id != user_id:
                db.add(DeclinedPair(user_id=user_id, other_id=other.user_id))
    db.flush()
    _settle(db, c)
    db.commit()
    return c


def leave(db: Session, c: Circle, user_id: int) -> Circle:
    if c.status == CircleStatus.dissolved:
        raise CircleError("This circle has already ended")
    m = membership(c, user_id)
    if m.status not in LIVE:
        raise CircleError("You are not in this circle")
    m.status = MemberStatus.left
    db.flush()
    _settle(db, c)
    db.commit()
    return c


def dissolve(db: Session, c: Circle, reason: str) -> Circle:
    if c.status == CircleStatus.dissolved:
        raise CircleError("Already ended")
    _dissolve(db, c, reason)
    db.commit()
    return c


def expire_if_stale(db: Session, c: Circle) -> bool:
    if c.status != CircleStatus.proposed:
        return False
    created = c.created_at if c.created_at.tzinfo else c.created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created > timedelta(days=PROPOSAL_DAYS):
        _dissolve(db, c, "Not everyone answered within 3 days")
        db.commit()
        return True
    return False


def set_mode(db: Session, c: Circle, mode: str) -> Circle:
    if mode not in travel_modes(group_of(c)):
        raise CircleError("Not everyone in the circle travels that way")
    c.mode = mode
    rota.regenerate(db, c, keep_manual=False)
    db.commit()
    return c


def remove_user_everywhere(db: Session, user: User) -> None:
    """Used when a student is suspended or deletes their account."""
    for c in live_circles_of(db, user.id):
        membership(c, user.id).status = MemberStatus.left
        db.flush()
        _settle(db, c)


def profile_changed(db: Session, user: User) -> str | None:
    c = next(iter(live_circles_of(db, user.id)), None)
    if not c:
        return None
    rota.regenerate(db, c)
    if not feasible(group_of(c), rules_for(db)):
        return "Your new answers no longer fit your circle well. Talk to your circle, or re-match."
    return None
