"""Student screens: Find my circle, Today, My circle, Money, My savings (prototype tabs)."""
from __future__ import annotations

from statistics import median

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..areas import area_coords, short_area
from ..config import settings
from ..db import get_db
from ..deps import current_user
from ..matching.compat import DAYS, DRIVE_MODES, METHODS, circle_fit, fit_label, group_days, pair_fit, travel_modes
from ..models import (Absence, Circle, CircleStatus, Feedback, MemberStatus, Report, RotaEntry, SeatRequest,
                      SeatStatus, Settlement, Trip, TripStatus, User)
from ..schemas import (AcceptIn, DayIn, FareIn, FeedbackIn, GoingIn, ModeIn, ReportIn, RespondIn, SeatIn, SettleIn,
                       TripIn)
from ..services import circles as svc
from ..services import clock, rota, trips
from ..services.candidates import LIVE, live_circles_of, rules_for, to_candidate

router = APIRouter(prefix="/api", tags=["student"])
CAMPUS = lambda: (settings.campus_lat, settings.campus_lng)  # noqa: E731


def short(name: str) -> str:
    p = name.split()
    return f"{p[0]} {p[1][0]}." if len(p) > 1 else p[0]


def prog(p) -> str:
    return (p.programme or "").split(" (")[0]


def _err(fn, *a):
    try:
        return fn(*a)
    except svc.CircleError as e:
        raise HTTPException(409, str(e)) from e


def my_circle(db: Session, user: User, active_only: bool = False) -> Circle | None:
    cs = live_circles_of(db, user.id)
    for c in cs:
        svc.expire_if_stale(db, c)
    cs = [c for c in cs if c.status != CircleStatus.dissolved]
    act = next((c for c in cs if c.status == CircleStatus.active), None)
    if active_only:
        return act
    return next((c for c in cs if c.status == CircleStatus.proposed), None) or act


def need_circle(db, user) -> Circle:
    c = my_circle(db, user, active_only=True)
    if not c:
        raise HTTPException(404, "You are not in a circle yet")
    return c


# --- Trip questions & Find my circle -----------------------------------------

@router.get("/trip")
def get_trip(user: User = Depends(current_user)):
    p = user.profile
    on = [d for d in DAYS if d in (p.schedule or {})]
    first = p.schedule[on[0]] if on else {"in": "08:30", "out": "14:00"}
    return {"area": p.area or None, "days": on, "arrive": first["in"], "leave": first["out"],
            "women_only": p.women_only, "methods": p.methods or [], "has_car": p.has_car, "seats": p.seats,
            "schedule": p.schedule or {}, "gender": p.gender.value}


@router.put("/trip")
def put_trip(body: TripIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = user.profile
    p.area, p.methods, p.has_car, p.seats = body.area, body.methods, body.has_car, body.seats
    p.women_only = body.women_only and p.gender.value == "female"
    p.schedule = body.schedule()
    db.flush()
    warning = svc.profile_changed(db, user)
    db.commit()
    return {"ok": True, "warning": warning}


def _option_out(db, user, grp) -> dict:
    from ..matching.compat import route_info

    me = grp[0]
    info = route_info(grp, CAMPUS(), settings.road_factor)
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_([c.user_id for c in grp])))}
    fit = circle_fit(grp, CAMPUS())
    mode = travel_modes(grp)[0]
    members = []
    for n, uid in enumerate(info["order"]):
        c = next(x for x in grp if x.user_id == uid)
        u = users[uid]
        p = pair_fit(me, c, CAMPUS()) if c is not me else None
        members.append({
            "user_id": uid, "name": "You" if c is me else short(u.full_name), "programme": prog(u.profile),
            "area": u.profile.area, "pickup": n + 1, "me": c is me,
            "km": round(p.km, 1) if p else None, "same_area": bool(p and p.km < 0.3),
            "on_way": bool(p and p.on_way), "days_match": len(p.good_days) if p else None,
            "coords": area_coords(u.profile.area),
        })
    rate = trips.rate_for("Shared ride-hailing")
    return {"member_ids": [c.user_id for c in grp], "fit": fit, "label": fit_label(fit), "size": len(grp),
            "days": group_days(grp, settings.schedule_window_min), "mode": mode, "members": members,
            "road_km": round(info["road_km"], 1),
            "solo_fare": round(trips.solo(user, "Shared ride-hailing")),
            "share_est": round(info["road_km"] * rate / len(grp))}


@router.get("/find/options")
def find_options(user: User = Depends(current_user), db: Session = Depends(get_db)):
    opts = _err(svc.find_options, db, user)
    me = to_candidate(user.profile)
    others = [c for c in _err(svc.find_pool, db, user) if c.user_id != user.id]
    from ..matching.compat import allowed

    return {"options": [_option_out(db, user, g) for g in opts],
            "others": [list(c.location) for c in others if allowed(me, c)
                       and not any(c.user_id in [x.user_id for x in g] for g in opts[:1])],
            "women_only": me.women_only}


@router.post("/find/accept")
def find_accept(body: AcceptIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = _err(svc.accept_option, db, user, body.member_ids)
    return {"circle_id": c.id, "status": c.status.value}


# --- My circle ---------------------------------------------------------------

def _member_out(db, c: Circle, u: User, me: User, pickup: int, reveal: bool) -> dict:
    st = trips.user_stats(db, u)
    return {"user_id": u.id, "name": "You" if u.id == me.id else short(u.full_name), "full_name": u.full_name,
            "me": u.id == me.id, "programme": prog(u.profile), "year": u.profile.year, "area": u.profile.area,
            "phone": u.phone if reveal and u.id != me.id else None, "pickup": pickup,
            "status": next(m.status.value for m in c.members if m.user_id == u.id),
            "reliability": st["reliability"], "trips": st["went"], "badges": st["badges"],
            "coords": area_coords(u.profile.area)}


def circle_out(db: Session, c: Circle, me: User) -> dict:
    live = [m for m in c.members if m.status in LIVE]
    users = {m.user_id: m.user for m in live}
    order = trips.circle_route(c)["order"]
    reveal = c.status == CircleStatus.active
    td = trips.travel_days(c)
    plan = {}
    for d in DAYS:
        on = {u.id for u in trips.plans_on(c, d)} if d in td else set()
        plan[d] = {uid: users[uid].profile.schedule[d]["in"] if uid in on else None for uid in order}
    today = clock.today()
    rota_rows = []
    if c.mode in DRIVE_MODES and c.status == CircleStatus.active:
        for e in db.scalars(select(RotaEntry).where(RotaEntry.circle_id == c.id, RotaEntry.day >= today)
                            .order_by(RotaEntry.day)).all()[:10]:
            u = db.get(User, e.user_id) if e.user_id else None
            rota_rows.append({"day": e.day.isoformat(), "user_id": e.user_id,
                              "name": ("You" if u and u.id == me.id else short(u.full_name)) if u else None})
    mine = next(m for m in c.members if m.user_id == me.id)
    return {
        "id": c.id, "status": c.status.value, "my_status": mine.status.value, "mode": c.mode,
        "modes": travel_modes(svc.group_of(c)) if len(live) >= 2 else [c.mode],
        "since": c.since.isoformat() if c.since else None, "fit": c.fit, "label": fit_label(c.fit),
        "members": [_member_out(db, c, users[uid], me, n + 1, reveal) for n, uid in enumerate(order)],
        "travel_days": td, "plan": plan, "rota": rota_rows,
        "road_km": round(trips.circle_route(c)["road_km"], 1),
        "whatsapp_name": f"CommuteCircle · {short_area(users[order[0]].profile.area)} → BIC" if order else "",
        "share_hint": round(max(50, trips.solo(me, "Shared ride-hailing") / max(2, len(live)))),
        "is_driver_mode": c.mode in DRIVE_MODES,
    }


@router.get("/circle")
def get_circle(user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = my_circle(db, user)
    db.commit()
    return circle_out(db, c, user) if c else None


@router.post("/circle/respond")
def respond(body: RespondIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = my_circle(db, user)
    if not c or c.status != CircleStatus.proposed:
        raise HTTPException(404, "No circle is waiting for your answer")
    _err(svc.respond, db, c, user.id, body.accept)
    return {"status": c.status.value}


@router.post("/circle/leave")
def leave(user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = my_circle(db, user)
    if not c:
        raise HTTPException(404, "You are not in a circle")
    _err(svc.leave, db, c, user.id)
    return {"ok": True}


@router.patch("/circle/mode")
def set_mode(body: ModeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = need_circle(db, user)
    _err(svc.set_mode, db, c, body.mode)
    return circle_out(db, c, user)


@router.post("/circle/rota/take")
def rota_take(body: DayIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = need_circle(db, user)
    try:
        rota.take(db, c, user.id, body.day)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    return circle_out(db, c, user)


@router.post("/circle/rota/cant")
def rota_cant(body: DayIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = need_circle(db, user)
    rota.cant_do(db, c, user.id, body.day)
    db.commit()
    return circle_out(db, c, user)


@router.post("/circle/feedback", status_code=201)
def feedback(body: FeedbackIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = need_circle(db, user)
    if body.to_id == user.id or body.to_id not in [m.user_id for m in c.members if m.status in LIVE]:
        raise HTTPException(403, "You can only give feedback about members of your circle")
    if body.tag not in (trips.TAGS if body.up else trips.NEG_TAGS):
        raise HTTPException(422, "Pick one of the options")
    db.add(Feedback(from_id=user.id, to_id=body.to_id, circle_id=c.id, up=body.up, tag=body.tag))
    if not body.up and body.tag == "Didn’t turn up":
        trips.mark_noshow_from_feedback(db, c, body.to_id)
    db.commit()
    return {"ok": True}


@router.post("/circle/report", status_code=201)
def report(body: ReportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = my_circle(db, user)
    shared = c and body.reported_id in [m.user_id for m in c.members] and body.reported_id != user.id
    if not shared:
        raise HTTPException(403, "You can only report members of your circle")
    db.add(Report(reporter_id=user.id, reported_id=body.reported_id, circle_id=c.id, reason=body.reason,
                  details=body.details or "No details given."))
    db.flush()
    if body.leave:
        svc.leave(db, c, user.id)
    db.commit()
    return {"ok": True}


# --- Today -------------------------------------------------------------------

@router.get("/today")
def today_view(user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = need_circle(db, user)
    day = clock.today()
    t = trips.ensure_trip(db, c, day)
    mine = trips.status_of(t, user.id) if t else None
    order = trips.circle_route(c)["order"]
    users = {m.user_id: m.user for m in c.members}
    went = trips.went_count(t) if t else 0
    trip = None
    if t and mine is not None:
        conf = db.get(User, t.confirmed_by) if t.confirmed_by else None
        share = (t.total / went) if (t.total and t.total > 0 and went) else None
        trip = {
            "confirmed": bool(t.confirmed_by), "confirmed_by_me": t.confirmed_by == user.id,
            "confirmed_by": ("You" if conf and conf.id == user.id else short(conf.full_name)) if conf else None,
            "my_status": mine.value, "went": went, "mode": t.mode,
            "share": round(share) if share else None,
            "saved": round(max(0, trips.solo(user, t.mode) - share)) if share else None,
            "ask_fare": bool(t.confirmed_by == user.id and t.total is None and not t.fare_skipped
                             and mine == TripStatus.went and trips.rate_for(t.mode) > 0),
            "suggestions": trips.share_suggestions(db, user, c),
            "payers": [{"user_id": m.user_id, "name": "Me" if m.user_id == user.id else short(db.get(User, m.user_id).full_name)}
                       for m in t.members if m.status == TripStatus.went],
            "demo_other": next((short(users[m.user_id].full_name) for m in t.members
                                if m.user_id != user.id and m.status == TripStatus.planned), None),
        }
    labels = {"planned": "Planned", "went": "Travelled", "notgoing": "Not going", "noshow": "Didn’t turn up"}
    members = []
    for n, uid in enumerate(order):
        st = trips.status_of(t, uid) if t else None
        members.append({"user_id": uid, "name": "You" if uid == user.id else short(users[uid].full_name),
                        "me": uid == user.id, "area": users[uid].profile.area, "pickup": n + 1,
                        "status": st.value if st else None,
                        "label": "" if (st == TripStatus.planned and t.confirmed_by) else labels.get(st.value, "") if st else "Not planned",
                        "coords": area_coords(users[uid].profile.area)})
    tom = clock.next_weekday(day)
    tom_plan = trips.planned_on(db, c, user, tom) or bool(db.scalar(select(Absence).filter_by(user_id=user.id, day=tom)))
    off = bool(db.scalar(select(Absence).filter_by(user_id=user.id, day=tom)))
    tdn = clock.day_name(tom)
    rt = db.scalar(select(RotaEntry).filter_by(circle_id=c.id, day=day)) if c.mode in DRIVE_MODES else None
    guest = trips.guest_seat(db, user.id, day)
    host = db.get(Circle, guest.circle_id) if guest else None
    st = trips.user_stats(db, user)
    pending_seats = db.scalars(select(SeatRequest).filter_by(circle_id=c.id, day=day, status=SeatStatus.pending)).all()
    db.commit()
    return {
        "date": day.isoformat(), "weekday": clock.day_name(day), "trip": trip, "members": members,
        "mode": c.mode, "road_km": round(trips.circle_route(c)["road_km"], 1), "travel_days": trips.travel_days(c),
        "rota_today": ({"user_id": rt.user_id, "me": rt.user_id == user.id,
                        "name": short(db.get(User, rt.user_id).full_name) if rt.user_id else None}
                       if rt and mine is not None else None),
        "tomorrow": {"date": tom.isoformat(), "planned": tom_plan, "off": off,
                     "arrive": user.profile.schedule.get(tdn, {}).get("in") if tdn else None},
        "tiles": {"streak": trips.streak(db, c), "went": st["went"], "saved": st["saved"], "reliability": st["reliability"]},
        "guest": ({"seat_id": guest.id, "members": [short(u.full_name) for u in trips._live_users(host)]}
                  if guest else None),
        "seat_requests": [{"id": s.id, "name": short(db.get(User, s.user_id).full_name),
                           "area": db.get(User, s.user_id).profile.area} for s in pending_seats],
        "my_seat_request": next(({"id": s.id, "status": s.status.value} for s in db.scalars(
            select(SeatRequest).filter_by(user_id=user.id, day=day, status=SeatStatus.pending))), None),
    }


def _today_trip(db, user) -> tuple[Circle, Trip]:
    c = need_circle(db, user)
    t = trips.ensure_trip(db, c, clock.today())
    if not t or trips.status_of(t, user.id) is None:
        raise HTTPException(409, "No circle trip is planned for you today")
    return c, t


@router.post("/today/yes")
def today_yes(user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, t = _today_trip(db, user)
    if t.confirmed_by:
        raise HTTPException(409, "Today's trip is already confirmed")
    trips.set_status(t, user.id, TripStatus.planned)
    trips.confirm(t, user.id)
    db.commit()
    return {"ok": True}


@router.post("/today/no")
def today_no(user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, t = _today_trip(db, user)
    trips.set_status(t, user.id, TripStatus.notgoing)
    db.commit()
    return {"ok": True}


@router.post("/today/correct")
def today_correct(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """'Not me? I didn't go' / 'Actually, I did go' after someone else confirmed."""
    _, t = _today_trip(db, user)
    if not t.confirmed_by:
        raise HTTPException(409, "Today's trip has not been confirmed yet")
    cur = trips.status_of(t, user.id)
    trips.set_status(t, user.id, TripStatus.notgoing if cur == TripStatus.went else TripStatus.went)
    db.commit()
    return {"ok": True}


@router.post("/today/fare")
def today_fare(body: FareIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, t = _today_trip(db, user)
    if t.confirmed_by != user.id:
        raise HTTPException(403, "Only the member who confirmed can enter the fare")
    if body.skip:
        t.fare_skipped = True
    else:
        travellers = [m.user_id for m in t.members if m.status == TripStatus.went]
        payer = body.payer_id or user.id
        if payer not in travellers:
            raise HTTPException(422, "The payer must be someone who travelled")
        t.total, t.payer_id = body.share * len(travellers), payer
    db.commit()
    return {"ok": True}


@router.post("/tomorrow")
def tomorrow(body: GoingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    need_circle(db, user)
    tom = clock.next_weekday(clock.today())
    row = db.scalar(select(Absence).filter_by(user_id=user.id, day=tom))
    if body.going and row:
        db.delete(row)
    elif not body.going and not row:
        db.add(Absence(user_id=user.id, day=tom))
    db.commit()
    return {"ok": True}


# --- One-day seats -----------------------------------------------------------

@router.get("/seats")
def seat_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    own = my_circle(db, user, active_only=True)
    return [{"circle_id": o["circle"].id, "members": [short(u.full_name) for u in o["members"]],
             "area": o["members"][0].profile.area, "near_km": o["near_km"], "on_way": o["on_way"],
             "arrive": o["arrive"], "free": o["free"]}
            for o in trips.seat_options(db, user, clock.today(), own)]


@router.post("/seats", status_code=201)
def seat_request(body: SeatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    own = my_circle(db, user, active_only=True)
    day = clock.today()
    if body.circle_id not in [o["circle"].id for o in trips.seat_options(db, user, day, own)]:
        raise HTTPException(409, "That circle has no free seat for you today")
    db.add(SeatRequest(user_id=user.id, circle_id=body.circle_id, day=day))
    db.commit()
    return {"ok": True}


@router.post("/seats/{seat_id}/answer")
def seat_answer(seat_id: int, body: RespondIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(SeatRequest, seat_id)
    c = my_circle(db, user, active_only=True)
    if not s or not c or s.circle_id != c.id or s.status != SeatStatus.pending:
        raise HTTPException(404, "Seat request not found")
    s.status, s.answered_by = (SeatStatus.accepted if body.accept else SeatStatus.declined), user.id
    if body.accept:
        t = trips.ensure_trip(db, c, s.day)
        if t and trips.status_of(t, s.user_id) is None:
            from ..models import TripMember

            t.members.append(TripMember(user_id=s.user_id, guest=True))
        guest_own = my_circle(db, db.get(User, s.user_id), active_only=True)
        if guest_own:
            gt = trips.ensure_trip(db, guest_own, s.day)
            if gt and trips.status_of(gt, s.user_id) is not None:
                trips.set_status(gt, s.user_id, TripStatus.notgoing)
    db.commit()
    return {"ok": True}


@router.post("/seats/{seat_id}/cancel")
def seat_cancel(seat_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(SeatRequest, seat_id)
    if not s or s.user_id != user.id or s.status not in (SeatStatus.pending, SeatStatus.accepted):
        raise HTTPException(404, "Seat request not found")
    s.status = SeatStatus.cancelled
    host = db.get(Circle, s.circle_id)
    t = trips.trip_on(db, host, s.day) if host else None
    if t:
        t.members = [m for m in t.members if not (m.user_id == user.id and m.guest)]
    own = my_circle(db, user, active_only=True)
    ot = trips.trip_on(db, own, s.day) if own else None
    if ot and trips.status_of(ot, user.id) == TripStatus.notgoing and not ot.confirmed_by:
        trips.set_status(ot, user.id, TripStatus.planned)
    db.commit()
    return {"ok": True}


# --- Money -------------------------------------------------------------------

@router.get("/money")
def money(user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = need_circle(db, user)
    net = trips.balances(db, c)
    names = {m.user_id: ("You" if m.user_id == user.id else short(m.user.full_name)) for m in c.members}
    lines = [x | {"from": names.get(x["from_id"]), "to": names.get(x["to_id"])} for x in trips.settle_lines(net)
             if user.id in (x["from_id"], x["to_id"])]
    q = select(Trip).where(Trip.circle_id == c.id, Trip.total > 0, Trip.payer_id.is_not(None),
                           Trip.confirmed_by.is_not(None)).order_by(Trip.day.desc())
    if c.settled_until:
        q = q.where(Trip.day > c.settled_until)
    recent = []
    for t in db.scalars(q):
        mine = trips.status_of(t, user.id) == TripStatus.went
        recent.append({"day": t.day.isoformat(), "payer": names.get(t.payer_id, "Former member"), "total": t.total,
                       "my_share": round(t.total / trips.went_count(t)) if mine else None})
    return {"balance": round(net.get(user.id, 0.0)), "settled_until": c.settled_until.isoformat() if c.settled_until else None,
            "lines": lines, "members": [{"user_id": m.user_id, "name": names[m.user_id], "net": round(net.get(m.user_id, 0))}
                                        for m in c.members if m.status in LIVE],
            "recent": recent}


@router.post("/money/settle")
def money_settle(body: SettleIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = need_circle(db, user)
    if user.id not in (body.from_id, body.to_id):
        raise HTTPException(403, "You can only settle your own balances")
    db.add(Settlement(circle_id=c.id, from_id=body.from_id, to_id=body.to_id, amount=body.amount))
    db.commit()
    return {"ok": True}


@router.post("/money/settle-all")
def money_settle_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = need_circle(db, user)
    trips.settle_all(db, c)
    db.commit()
    return {"ok": True}


# --- My savings --------------------------------------------------------------

@router.get("/savings")
def savings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..models import TripMember

    st = trips.user_stats(db, user)
    past = clock.past_weekdays(20)
    weeks = []
    for i in range(4):
        ws = set(past[i * 5:(i + 1) * 5])
        paid = solo_ = 0.0
        q = select(TripMember, Trip).join(Trip).where(TripMember.user_id == user.id, TripMember.status == TripStatus.went,
                                                      Trip.confirmed_by.is_not(None), Trip.total > 0)
        for tm, t in db.execute(q):
            if t.day in ws:
                paid += t.total / trips.went_count(t)
                solo_ += trips.solo(user, t.mode)
        weeks.append({"label": f"Week {i + 1}", "paid": round(paid), "solo": round(solo_)})
    guide = []
    if user.profile.area:
        for md in METHODS:
            if trips.rate_for(md) <= 0:
                continue
            v = trips.route_fares(db, user.profile.area, md)
            guide.append({"mode": md, "n": len(v), "median": round(median(v)) if v else None,
                          "lo": round(min(v)) if v else None, "hi": round(max(v)) if v else None})
    return {"tiles": st, "weeks": weeks, "guide": guide, "area": user.profile.area,
            "in_circle": my_circle(db, user, active_only=True) is not None}
