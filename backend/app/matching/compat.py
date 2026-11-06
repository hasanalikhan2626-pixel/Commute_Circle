"""Compatibility rules (ported from the CommuteCircle prototype).

Fit score for a pair, 0-100, from student A's point of view:
  * Route     40  0% detour -> 40, 35%+ detour -> 0
  * Nearby    20  <=1.5 km apart -> 20, >=8 km -> 0
  * Timetable 30  for each of A's days: arrival within 15 min = 1, 30 min = 0.5
                  (70%), leaving time the same way (30%)
  * Travel    10  at least one way of travelling in common

Hard rules for a circle:
  * 2-4 members; women-only students are only grouped with women
  * every pair scores at least ``pair_min`` (35) with at least one good day
  * at least one weekday on which everyone arrives within ``window`` (20) minutes
    of the circle's first member
  * a way of travelling everyone accepts; "Classmate drives" also needs a member
    with a car and enough seats
  * no pair that a student previously declined
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from .geo import detour_ratio, haversine_km, pickup_route_km
from .types import Candidate

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
METHODS = ("Shared ride-hailing", "Classmate drives", "Family driver", "Parent drop", "Rickshaw")
DRIVE_MODES = ("Classmate drives", "Family driver", "Parent drop")  # these get a rota
MIN_FIT = 45


def minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def to_hhmm(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


@dataclass(frozen=True)
class Rules:
    campus: tuple[float, float]
    window_min: int = 20
    min_fit: int = MIN_FIT
    pair_min: int = MIN_FIT - 10
    max_circle_size: int = 4
    excluded: frozenset = field(default_factory=frozenset)


@dataclass(frozen=True)
class PairFit:
    total: int
    route: int
    near: int
    sched: int
    pref: int
    km: float
    detour: float
    good_days: tuple[str, ...]
    common: tuple[str, ...]
    on_way: bool


def allowed(a: Candidate, b: Candidate) -> bool:
    if a.women_only and b.gender != "female":
        return False
    if b.women_only and a.gender != "female":
        return False
    return True


def _slot(v: int) -> float:
    return 1.0 if v <= 15 else 0.5 if v <= 30 else 0.0


def pair_fit(a: Candidate, b: Candidate, campus: tuple[float, float]) -> PairFit | None:
    if not allowed(a, b):
        return None
    d = haversine_km(a.location, b.location)
    det = detour_ratio(a.location, b.location, campus)
    route = max(0.0, 40 * (1 - det / 0.35))
    near = min(20.0, max(0.0, 20 * (1 - (d - 1.5) / 6.5)))
    my_days = [x for x in DAYS if x in a.schedule]
    oks = []
    for x in my_days:
        if x not in b.schedule:
            oks.append((x, 0.0))
            continue
        di = abs(minutes(a.schedule[x]["in"]) - minutes(b.schedule[x]["in"]))
        do = abs(minutes(a.schedule[x]["out"]) - minutes(b.schedule[x]["out"]))
        oks.append((x, _slot(di) * 0.7 + _slot(do) * 0.3))
    sched = 30 * sum(o for _, o in oks) / len(my_days) if my_days else 0.0
    common = tuple(m for m in a.methods if m in b.methods)
    pref = 10 if common else 0
    return PairFit(
        total=round(route + near + sched + pref), route=round(route), near=round(near), sched=round(sched),
        pref=pref, km=d, detour=det, good_days=tuple(x for x, o in oks if o >= 0.7), common=common,
        on_way=det <= 0.12,
    )


def group_days(group: list[Candidate], window: int) -> list[str]:
    """Days on which every member is on campus within ``window`` minutes of the first member."""
    ref = group[0]
    return [d for d in DAYS if all(d in s.schedule for s in group)
            and all(abs(minutes(s.schedule[d]["in"]) - minutes(ref.schedule[d]["in"])) <= window for s in group)]


def travel_modes(group: list[Candidate]) -> list[str]:
    """Ways of travelling every member accepts and that can carry the whole group."""
    out = []
    for m in METHODS:
        if not all(m in s.methods for s in group):
            continue
        if m == "Classmate drives" and not any(s.has_car and s.seats >= len(group) - 1 for s in group):
            continue
        out.append(m)
    return out


def pair_ok(a: Candidate, b: Candidate, rules: Rules) -> bool:
    if frozenset((a.user_id, b.user_id)) in rules.excluded:
        return False
    for x, y in ((a, b), (b, a)):
        p = pair_fit(x, y, rules.campus)
        if p is None or p.total < rules.pair_min or not p.good_days:
            return False
    return True


def feasible(group: list[Candidate], rules: Rules) -> bool:
    if not 2 <= len(group) <= rules.max_circle_size:
        return False
    if not all(pair_ok(a, b, rules) for a, b in combinations(group, 2)):
        return False
    return bool(group_days(group, rules.window_min)) and bool(travel_modes(group))


def circle_fit(group: list[Candidate], campus: tuple[float, float]) -> int:
    scores = [(pair_fit(a, b, campus) or PairFit(0, 0, 0, 0, 0, 0, 0, (), (), False)).total
              for a, b in combinations(group, 2)]
    return round(sum(scores) / len(scores)) if scores else 0


def fit_label(v: int) -> str:
    return "Great fit" if v >= 75 else "Good fit" if v >= 60 else "Fair fit"


def route_info(group: list[Candidate], campus: tuple[float, float], road_factor: float) -> dict:
    order, km = pickup_route_km([s.location for s in group], campus)
    return {"order": [group[i].user_id for i in order], "road_km": km * road_factor}
