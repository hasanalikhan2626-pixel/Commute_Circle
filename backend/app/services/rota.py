"""Fair rota for the driving modes (Classmate drives, Family driver, Parent drop).

For each travel day in the next two weeks, the turn goes to the eligible member with
the fewest turns so far in this circle (ties: who went least recently, then id).
Days someone took or swapped by hand are kept.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..matching.compat import DRIVE_MODES
from ..models import Circle, CircleStatus, MemberStatus, RotaEntry, RotaUnavailable
from . import clock

AHEAD_DAYS = 14


def eligible(c: Circle) -> list[int]:
    live = [m for m in c.members if m.status in (MemberStatus.accepted, MemberStatus.pending) and m.user.profile]
    if c.mode == "Classmate drives":
        ids = [m.user_id for m in live if m.user.profile.has_car]
    else:
        ids = [m.user_id for m in live if c.mode in (m.user.profile.methods or [])]
    return ids or [m.user_id for m in live]


def rota_days(c: Circle, start: date) -> list[date]:
    from .trips import travel_days

    days = set(travel_days(c))
    return [start + timedelta(d) for d in range(AHEAD_DAYS) if clock.day_name(start + timedelta(d)) in days]


def regenerate(db: Session, c: Circle, today: date | None = None, keep_manual: bool = True) -> None:
    today = today or clock.today()
    future = delete(RotaEntry).where(RotaEntry.circle_id == c.id, RotaEntry.day >= today)
    if c.status != CircleStatus.active or c.mode not in DRIVE_MODES:
        db.execute(future)  # no rota for ride-hailing, rickshaw or ended circles
        db.flush()
        db.expire(c, ["rota"])
        return
    db.execute(future.where(RotaEntry.manual.is_(False)) if keep_manual else future)
    db.flush()
    who = eligible(c)
    entries = db.scalars(select(RotaEntry).where(RotaEntry.circle_id == c.id)).all()
    turns = Counter(e.user_id for e in entries if e.user_id in who)
    last = {e.user_id: e.day for e in sorted(entries, key=lambda e: e.day)}
    taken = {e.day for e in entries if e.day >= today}
    off = {(u.user_id, u.day) for u in db.scalars(select(RotaUnavailable).where(RotaUnavailable.circle_id == c.id))}
    for d in rota_days(c, today):
        if d in taken:
            continue
        avail = [u for u in who if (u, d) not in off] or who
        pick = min(avail, key=lambda u: (turns[u], last.get(u, date.min), u))
        turns[pick] += 1
        last[pick] = d
        db.add(RotaEntry(circle_id=c.id, day=d, user_id=pick))
    db.flush()
    db.expire(c, ["rota"])


def cant_do(db: Session, c: Circle, user_id: int, d: date) -> None:
    if not db.scalar(select(RotaUnavailable).filter_by(circle_id=c.id, user_id=user_id, day=d)):
        db.add(RotaUnavailable(circle_id=c.id, user_id=user_id, day=d))
    entry = db.scalar(select(RotaEntry).filter_by(circle_id=c.id, day=d))
    if entry and entry.user_id == user_id:
        others = [u for u in eligible(c) if u != user_id] or [m.user_id for m in c.members
                                                              if m.user_id != user_id and m.status in (MemberStatus.accepted,)]
        if others:
            counts = Counter(e.user_id for e in c.rota)
            entry.user_id = min(others, key=lambda u: (counts[u], u))
            entry.manual = True
    db.flush()


def take(db: Session, c: Circle, user_id: int, d: date) -> None:
    entry = db.scalar(select(RotaEntry).filter_by(circle_id=c.id, day=d))
    if not entry:
        raise ValueError("No rota day on that date")
    entry.user_id, entry.manual = user_id, True
    db.execute(delete(RotaUnavailable).where(RotaUnavailable.circle_id == c.id, RotaUnavailable.user_id == user_id,
                                             RotaUnavailable.day == d))
    db.flush()
