"""Scheduled work, run by POST /api/jobs/run every 15 minutes (GitHub Actions; see docs/WHATSAPP.md).

* Reminder 45 minutes before arrival (sent in the 30-60 minute window to absorb schedule
  delays), proposal risk table: "automated WhatsApp reminders 45 minutes prior".
* Check-in after the circle's arrival time: "Reached campus? Reply 1 = Yes, 2 = Didn't go".
* Withdraw proposals nobody finished answering within 3 days.

Every message is de-duplicated per student per day, so re-running the job is harmless.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..areas import short_area
from ..matching.compat import minutes
from ..models import Circle, CircleStatus, TripStatus
from . import circles as svc
from . import clock, notify, trips


def _first(name: str) -> str:
    return name.split()[0]


def run(db: Session) -> dict:
    now = clock.now()
    day = now.date()
    dn = clock.day_name(day)
    out = {"reminders": 0, "checkins": 0, "expired": 0, "date": day.isoformat(), "time": now.strftime("%H:%M")}
    for c in db.scalars(select(Circle).where(Circle.status == CircleStatus.proposed)).all():
        out["expired"] += int(svc.expire_if_stale(db, c))
    if not dn:
        db.commit()
        return out
    mins_now = now.hour * 60 + now.minute
    for c in db.scalars(select(Circle).where(Circle.status == CircleStatus.active)).all():
        if dn not in trips.travel_days(c):
            continue
        arrive = trips.arrive_time(c, dn)
        if not arrive:
            continue
        a = minutes(arrive)
        route = trips.circle_route(c)
        names = {m.user_id: m.user for m in c.members}
        order = " → ".join(short_area(names[u].profile.area) for u in route["order"] if u in names)
        planned = [u for u in trips._live_users(c) if trips.planned_on(db, c, u, day)]
        for u in planned:
            if not (u.whatsapp_opt_in and u.phone):
                continue
            if 30 <= a - mins_now <= 60:
                n = notify.whatsapp(db, u.phone, "cc_reminder", [_first(u.full_name), arrive, order],
                                    user_id=u.id, dedupe=f"rem:{u.id}:{day}")
                out["reminders"] += int(n is not None)
            elif mins_now >= a + 30 and mins_now <= 18 * 60:
                t = trips.ensure_trip(db, c, day)
                if t and not t.confirmed_by and trips.status_of(t, u.id) == TripStatus.planned:
                    n = notify.whatsapp(db, u.phone, "cc_checkin", [_first(u.full_name)],
                                        user_id=u.id, dedupe=f"chk:{u.id}:{day}")
                    out["checkins"] += int(n is not None)
    db.commit()
    return out


def notify_proposal(db: Session, c: Circle) -> None:
    """Tell invited, opted-in classmates that someone suggested a circle with them."""
    founder = next((m.user for m in c.members if m.position == 0), None)
    for m in c.members:
        u = m.user
        if m.position == 0 or not (u.whatsapp_opt_in and u.phone):
            continue
        notify.whatsapp(db, u.phone, "cc_proposal", [_first(u.full_name), _first(founder.full_name) if founder else "A classmate"],
                        user_id=u.id, dedupe=f"prop:{c.id}:{u.id}")

