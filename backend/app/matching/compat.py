"""Compatibility rules shared by every matching algorithm.

Hard constraints (a circle is infeasible if any fails):
  * at least one driver, and no more members than the largest car can carry
  * at most ``max_circle_size`` members
  * gender preference: if anyone asked for same-gender only, everyone in the
    circle must share their (disclosed) gender
  * the whole group shares at least ``min_shared_days`` days on which every
    member's arrival falls inside one ``window``-minute slot
  * the driver's detour to collect everyone stays under ``max_detour_km``
  * no pair that a student previously declined is put together again

Soft score (0..1, higher is better): weighted mix of schedule overlap and
proximity, averaged over every pair in the circle.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from .geo import detour_km, haversine_km
from .types import Candidate

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat")


def minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def to_hhmm(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


@dataclass(frozen=True)
class Rules:
    campus: tuple[float, float]
    window_min: int = 30
    min_shared_days: int = 2
    max_circle_size: int = 5
    max_detour_km: float = 6.0
    proximity_scale_km: float = 8.0  # pairs this far apart score 0 on proximity
    w_schedule: float = 0.6
    w_proximity: float = 0.4
    excluded: frozenset[frozenset[int]] = frozenset()


def gender_ok(group: list[Candidate]) -> bool:
    if not any(c.same_gender_only for c in group):
        return True
    genders = {c.gender for c in group}
    return len(genders) == 1 and "undisclosed" not in genders


def group_days(group: list[Candidate], window: int) -> list[str]:
    """Days on which every member is on campus and all arrivals fit one window."""
    out = []
    for d in DAYS:
        times = [minutes(c.schedule[d]["arrive"]) for c in group if d in c.schedule]
        if len(times) == len(group) and max(times) - min(times) <= window:
            out.append(d)
    return out


def pair_compatible(a: Candidate, b: Candidate, rules: Rules) -> bool:
    if frozenset((a.user_id, b.user_id)) in rules.excluded:
        return False
    if not gender_ok([a, b]):
        return False
    return len(group_days([a, b], rules.window_min)) >= rules.min_shared_days


def pair_score(a: Candidate, b: Candidate, rules: Rules) -> float:
    days_a, days_b = set(a.schedule), set(b.schedule)
    union = days_a | days_b
    shared = len(group_days([a, b], rules.window_min))
    sched = shared / len(union) if union else 0.0
    prox = max(0.0, 1.0 - haversine_km(a.location, b.location) / rules.proximity_scale_km)
    return rules.w_schedule * sched + rules.w_proximity * prox


def capacity(group: list[Candidate]) -> int:
    """Max people the group can move in one car (driver + passenger seats)."""
    seats = [c.seats for c in group if c.has_car]
    return (max(seats) + 1) if seats else 0


def best_detour(group: list[Candidate], rules: Rules) -> float:
    drivers = [c for c in group if c.has_car]
    if not drivers:
        return float("inf")
    return min(
        detour_km(d.location, [c.location for c in group if c is not d], rules.campus) for d in drivers
    )


def feasible(group: list[Candidate], rules: Rules) -> bool:
    if len(group) < 2 or len(group) > rules.max_circle_size:
        return False
    if len(group) > capacity(group):
        return False
    if not gender_ok(group):
        return False
    for a, b in combinations(group, 2):
        if frozenset((a.user_id, b.user_id)) in rules.excluded:
            return False
    if len(group_days(group, rules.window_min)) < rules.min_shared_days:
        return False
    return best_detour(group, rules) <= rules.max_detour_km


def can_grow(group: list[Candidate], rules: Rules) -> bool:
    """Feasibility test for partial circles that may still be a single driver."""
    if len(group) == 1:
        return group[0].has_car and group[0].seats > 0
    return feasible(group, rules)


def circle_score(group: list[Candidate], rules: Rules) -> float:
    pairs = list(combinations(group, 2))
    if not pairs:
        return 0.0
    return sum(pair_score(a, b, rules) for a, b in pairs) / len(pairs)
