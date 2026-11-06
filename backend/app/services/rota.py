"""Fair driving rota.

For every day the group commutes together, pick the available driver with the
fewest turns so far in this circle (ties broken by who drove least recently,
then by user id). This spreads driving evenly across drivers, unlike the
prototype, which always assigned the first driver.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..matching.compat import DAYS, group_days, minutes, to_hhmm
from ..models import Circle, CircleStatus, DriverUnavailability, MemberStatus, RotaEntry
from .candidates import to_candidate

ROTA_DAYS_AHEAD = 14


def active_members(circle: Circle):
    return [m for m in circle.members if m.status in (MemberStatus.accepted, MemberStatus.pending)]


def regenerate(db: Session, circle: Circle, today: date | None = None) -> None:
    """Rebuild the rota from ``today`` onward; past entries are kept as history."""
    today = today or date.today()
    db.execute(delete(RotaEntry).where(RotaEntry.circle_id == circle.id, RotaEntry.day >= today))
    db.flush()
    if circle.status != CircleStatus.active:
        return
    members = active_members(circle)
    profiles = [m.user.profile for m in members if m.user.profile]
    group = [to_candidate(p) for p in profiles]
    from ..config import settings

    days = set(group_days(group, settings.schedule_window_min))
    driver_ids = sorted(p.user_id for p in profiles if p.has_car and p.seats > 0)

    history = db.scalars(select(RotaEntry).where(RotaEntry.circle_id == circle.id, RotaEntry.day < today)).all()
    turns = Counter(e.driver_id for e in history if e.driver_id)
    last = {e.driver_id: e.day for e in history if e.driver_id}
    unavailable = {
        (u.user_id, u.day)
        for u in db.scalars(select(DriverUnavailability).where(DriverUnavailability.circle_id == circle.id))
    }

    for offset in range(ROTA_DAYS_AHEAD):
        day = today + timedelta(days=offset)
        if day.weekday() >= len(DAYS) or DAYS[day.weekday()] not in days:
            continue
        key = DAYS[day.weekday()]
        arrive = to_hhmm(min(minutes(p.schedule[key]["arrive"]) for p in profiles))
        available = [d for d in driver_ids if (d, day) not in unavailable]
        driver = None
        if available:
            driver = min(available, key=lambda d: (turns[d], last.get(d, date.min), d))
            turns[driver] += 1
            last[driver] = day
        db.add(RotaEntry(circle_id=circle.id, day=day, driver_id=driver, arrive=arrive))
    db.flush()
