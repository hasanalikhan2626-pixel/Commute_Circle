"""Daily trips, check-ins, money and stats (prototype Today / Money / My savings).

* A circle's travel days are weekdays on which at least two members arrive within
  the window of each other's anchor (the first member on campus that day).
* "Reached campus?" - one member confirming marks every planned member as travelled;
  anyone can correct their own record ("Not me? I didn't go").
* The confirmer may enter their share of the fare; it is multiplied by the number who
  travelled to get the total, and recorded against whoever paid.
* Balances: each traveller owes total / travellers; the payer is owed the total.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..areas import area_coords
from ..config import settings
from ..matching.compat import allowed, minutes, route_info
from ..matching.fares import rate, solo_fare
from ..matching.geo import detour_ratio, haversine_km
from ..models import (Absence, Circle, CircleStatus, Feedback, MemberStatus, SeatRequest, SeatStatus, Settlement,
                      Trip, TripMember, TripStatus, User)
from . import clock
from .candidates import LIVE, to_candidate

CAMPUS = lambda: (settings.campus_lat, settings.campus_lng)  # noqa: E731
TAGS = ("Punctual", "Friendly", "Good communicator", "Respectful")
NEG_TAGS = ("Didn’t turn up", "Very late", "Rude", "Other")


def _live_users(c: Circle) -> list[User]:
    return [m.user for m in c.members if m.status in LIVE and m.user.profile]


def _anchor_arrival(users: list[User], d: str) -> int | None:
    on = [u for u in users if d in (u.profile.schedule or {})]
    return minutes(on[0].profile.schedule[d]["in"]) if on else None


def plans_on(c: Circle, d: str) -> list[User]:
    """Members whose weekly plan puts them in this circle's trip on weekday ``d``."""
    users = _live_users(c)
    ref = _anchor_arrival(users, d)
    if ref is None:
        return []
    return [u for u in users if d in u.profile.schedule
            and abs(minutes(u.profile.schedule[d]["in"]) - ref) <= settings.schedule_window_min]


def travel_days(c: Circle) -> list[str]:
    from ..matching.compat import DAYS

    return [d for d in DAYS if len(plans_on(c, d)) >= 2]


def arrive_time(c: Circle, d: str) -> str | None:
    p = plans_on(c, d)
    return min((u.profile.schedule[d]["in"] for u in p), default=None)


def guest_seat(db: Session, user_id: int, day: date) -> SeatRequest | None:
    return db.scalar(select(SeatRequest).filter_by(user_id=user_id, day=day, status=SeatStatus.accepted))


def planned_on(db: Session, c: Circle, u: User, day: date) -> bool:
    d = clock.day_name(day)
    if not d or d not in travel_days(c) or u not in plans_on(c, d):
        return False
    if db.scalar(select(Absence).filter_by(user_id=u.id, day=day)):
        return False
    seat = guest_seat(db, u.id, day)
    return not (seat and seat.circle_id != c.id)


def trip_on(db: Session, c: Circle, day: date) -> Trip | None:
    return db.scalar(select(Trip).filter_by(circle_id=c.id, day=day))


def ensure_trip(db: Session, c: Circle, day: date) -> Trip | None:
    t = trip_on(db, c, day)
    if t or c.status != CircleStatus.active:
        return t
    planned = [u for u in _live_users(c) if planned_on(db, c, u, day)]
    if len(planned) < 1:
        return None
    t = Trip(circle_id=c.id, day=day, mode=c.mode)
    t.members = [TripMember(user_id=u.id) for u in planned]
    for s in db.scalars(select(SeatRequest).filter_by(circle_id=c.id, day=day, status=SeatStatus.accepted)):
        t.members.append(TripMember(user_id=s.user_id, guest=True))
    db.add(t)
    db.flush()
    return t


def status_of(t: Trip, user_id: int) -> TripStatus | None:
    return next((m.status for m in t.members if m.user_id == user_id), None)


def set_status(t: Trip, user_id: int, st: TripStatus) -> None:
    for m in t.members:
        if m.user_id == user_id:
            m.status = st
            return
    t.members.append(TripMember(user_id=user_id, status=st))


def went_count(t: Trip) -> int:
    return sum(1 for m in t.members if m.status == TripStatus.went)


def sharers(t: Trip) -> list[int]:
    """Who shares this trip's fare: everyone who travelled, except the payer when the payer is
    the provider in a passenger-pays mode (motorbike rider, host family)."""
    from ..matching.fares import PASSENGER_PAYS

    went = [m.user_id for m in t.members if m.status == TripStatus.went]
    if t.mode in PASSENGER_PAYS and t.payer_id in went and len(went) > 1:
        went = [u for u in went if u != t.payer_id]
    return went


def share_of(t: Trip, user_id: int) -> float | None:
    """This member's share of the trip's fare (None if no fare entered or they didn't pay in)."""
    if not (t.total and t.total > 0):
        return None
    s = sharers(t)
    return t.total / len(s) if user_id in s else None


def confirm(t: Trip, by: int) -> None:
    for m in t.members:
        if m.status == TripStatus.planned:
            m.status = TripStatus.went
    t.confirmed_by = by


def rate_for(mode: str) -> float:
    return rate(mode, settings.fuel_price_pkr, settings.fuel_km_per_litre)


def solo(u: User, mode: str) -> float:
    return solo_fare(area_coords(u.profile.area), CAMPUS(), mode, settings.road_factor,
                     settings.fuel_price_pkr, settings.fuel_km_per_litre)


def circle_route(c: Circle) -> dict:
    users = _live_users(c)
    return route_info([to_candidate(u.profile) for u in users], CAMPUS(), settings.road_factor) if users else \
        {"order": [], "road_km": 0.0}


# --- stats, badges, streaks -------------------------------------------------

def user_stats(db: Session, u: User) -> dict:
    went = ns = ng = trips14 = 0
    saved = paid = 0.0
    cut = clock.past_weekdays(10)[0]
    q = select(TripMember, Trip).join(Trip).where(TripMember.user_id == u.id)
    for tm, t in db.execute(q):
        if tm.status == TripStatus.went and t.confirmed_by:
            went += 1
            if t.day >= cut:
                trips14 += 1
            share = share_of(t, u.id)
            if share is not None and u.profile:
                paid += share
                saved += max(0.0, solo(u, t.mode) - share)
        elif tm.status == TripStatus.noshow:
            ns += 1
        elif tm.status == TripStatus.notgoing:
            ng += 1
    rel = round(went / (went + ns) * 100) if went + ns else None
    tags = Counter(f.tag for f in db.scalars(select(Feedback).where(Feedback.to_id == u.id, Feedback.up.is_(True))))
    badges = [k for k, v in tags.items() if v >= 2 and went >= 5]
    if rel is not None and rel >= 95 and went >= 5 and "Punctual" not in badges:
        badges.insert(0, "Reliable")
    return {"went": went, "noshow": ns, "notgoing": ng, "reliability": rel, "saved": round(saved),
            "paid": round(paid), "trips14": trips14, "badges": badges, "active": trips14 > 0}


def streak(db: Session, c: Circle) -> int:
    """Consecutive travel days (most recent first) with a confirmed trip."""
    td = set(travel_days(c))
    n = 0
    for d in reversed(clock.past_weekdays(40)):
        if c.since and d < c.since:
            break
        if clock.day_name(d) not in td:
            continue
        t = trip_on(db, c, d)
        if not (t and t.confirmed_by):
            break
        n += 1
    return n


# --- money ------------------------------------------------------------------

def balances(db: Session, c: Circle) -> dict[int, float]:
    net: dict[int, float] = {m.user_id: 0.0 for m in c.members}
    q = select(Trip).where(Trip.circle_id == c.id, Trip.confirmed_by.is_not(None), Trip.total > 0,
                           Trip.payer_id.is_not(None))
    if c.settled_until:
        q = q.where(Trip.day > c.settled_until)
    for t in db.scalars(q):
        who = sharers(t)
        if not who:
            continue
        for u in who:
            net[u] = net.get(u, 0.0) - t.total / len(who)
        net[t.payer_id] = net.get(t.payer_id, 0.0) + t.total
    for s in db.scalars(select(Settlement).where(Settlement.circle_id == c.id)):
        if s.from_id in net:
            net[s.from_id] += s.amount
        if s.to_id in net:
            net[s.to_id] -= s.amount
    return net


def settle_lines(net: dict[int, float]) -> list[dict]:
    deb = sorted(([u, -v] for u, v in net.items() if v < -5), key=lambda x: -x[1])
    cre = sorted(([u, v] for u, v in net.items() if v > 5), key=lambda x: -x[1])
    out, i, j = [], 0, 0
    while i < len(deb) and j < len(cre):
        a = min(deb[i][1], cre[j][1])
        out.append({"from_id": deb[i][0], "to_id": cre[j][0], "amount": round(a / 10) * 10})
        deb[i][1] -= a
        cre[j][1] -= a
        if deb[i][1] < 5:
            i += 1
        if cre[j][1] < 5:
            j += 1
    return [x for x in out if x["amount"] > 0]


def settle_all(db: Session, c: Circle) -> None:
    c.settled_until = clock.today()
    for s in db.scalars(select(Settlement).where(Settlement.circle_id == c.id)):
        db.delete(s)


def route_fares(db: Session, area: str, mode: str) -> list[float]:
    """Per-person shares entered for trips by members from ``area`` using ``mode``."""
    out = []
    q = select(Trip).where(Trip.mode == mode, Trip.total > 0, Trip.confirmed_by.is_not(None))
    for t in db.scalars(q):
        for uid in sharers(t):
            u = db.get(User, uid)
            if u and u.profile and u.profile.area == area:
                out.append(t.total / len(sharers(t)))
    return out


def circle_cost(c: Circle) -> dict:
    from ..matching.fares import cost_card

    return cost_card(c.mode, circle_route(c)["road_km"], max(2, len(_live_users(c))),
                     settings.fuel_price_pkr, settings.fuel_km_per_litre)


def share_suggestions(db: Session, u: User, c: Circle) -> list[int]:
    v = route_fares(db, u.profile.area, c.mode)
    md = median(v) if v else max(10.0, circle_cost(c)["per_person"])
    r = lambda x: max(10, round(x / 10) * 10)  # noqa: E731
    return [r(md * 0.85), r(md), r(md * 1.15)]


# --- one-day seats ----------------------------------------------------------

def seat_options(db: Session, u: User, day: date, own: Circle | None) -> list[dict]:
    from .candidates import approved_profiles  # noqa: F401  (import cycle guard)

    d = clock.day_name(day)
    if not d or not u.profile or d not in (u.profile.schedule or {}):
        return []
    me = to_candidate(u.profile)
    out = []
    for c in db.scalars(select(Circle).where(Circle.status == CircleStatus.active)):
        if own and c.id == own.id:
            continue
        users = _live_users(c)
        if not users or not all(allowed(me, to_candidate(x.profile)) for x in users) or d not in travel_days(c):
            continue
        going = [x for x in users if planned_on(db, c, x, day)]
        guests = db.scalars(select(SeatRequest).filter_by(circle_id=c.id, day=day, status=SeatStatus.accepted)).all()
        free = settings.max_circle_size - len(going) - len(guests)
        near = min(haversine_km(me.location, to_candidate(x.profile).location) for x in users)
        on_way = any(detour_ratio(me.location, to_candidate(x.profile).location, CAMPUS()) <= 0.12 for x in users)
        arrive = arrive_time(c, d)
        dt = abs(minutes(arrive) - minutes(u.profile.schedule[d]["in"])) if arrive else 999
        if free > 0 and (near <= 8 or on_way) and dt <= 30:
            out.append({"circle": c, "members": users, "near_km": round(near, 1), "on_way": on_way,
                        "arrive": arrive, "free": free})
    return sorted(out, key=lambda x: x["near_km"])[:3]


def mark_noshow_from_feedback(db: Session, c: Circle, user_id: int) -> None:
    """'Didn't turn up' feedback marks that member's latest recent confirmed trip as a no-show."""
    since = clock.today() - timedelta(days=7)
    q = (select(TripMember).join(Trip).where(Trip.circle_id == c.id, Trip.day >= since, Trip.confirmed_by.is_not(None),
                                             TripMember.user_id == user_id, TripMember.status == TripStatus.went)
         .order_by(Trip.day.desc()))
    tm = db.scalars(q).first()
    if tm:
        tm.status = TripStatus.noshow
