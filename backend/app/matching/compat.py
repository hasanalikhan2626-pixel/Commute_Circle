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
    with a car and enough seats; "Motorbike pillion" a member with a motorbike (2 people)
  * no pair that a student previously declined
  * no rider's estimated detour exceeds ``max_detour_min`` (12 minutes, proposal
    section 13): extra road km / assumed average speed
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from .geo import detour_ratio, haversine_km, pickup_route_km
from .types import Candidate

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
METHODS = ("Shared ride-hailing", "Classmate drives", "Family driver", "Parent drop", "Rickshaw", "Motorbike pillion")
DRIVE_MODES = ("Classmate drives", "Family driver", "Parent drop", "Motorbike pillion")  # these get a rota
# Passengers each way of travelling can carry (proposal Appendix C). "Classmate drives"
# depends on the driver's seats and is checked separately.
MODE_CAPACITY = {"Shared ride-hailing": 4, "Family driver": 4, "Parent drop": 4, "Rickshaw": 3, "Motorbike pillion": 2}
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
    # Proposal hard rule: no rider's estimated detour may exceed this (None = off).
    max_detour_min: float | None = 12.0
    speed_kmh: float = 22.0
    road_factor: float = 1.35


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
        if m == "Motorbike pillion" and not any(s.has_bike for s in group):
            continue
        if len(group) > MODE_CAPACITY.get(m, 99):
            continue
        out.append(m)
    return out


class Scorer:
    """Pair scores for one matching run.

    With ``pool`` given, every pair's fit is computed at once with NumPy (the same
    formula as ``pair_fit``), so scoring 500 students takes milliseconds instead of
    seconds. Students outside the pool fall back to ``pair_fit`` and are memoised.
    """

    def __init__(self, rules: Rules, pool: list[Candidate] | None = None):
        self.rules = rules
        self._fit: dict[tuple[int, int], PairFit | None] = {}
        self._ok: dict[tuple[int, int], bool] = {}
        self._arr: dict[int, dict[str, int]] = {}
        self._det: dict[frozenset, dict[int, float]] = {}
        self.idx: dict[int, int] = {}
        if pool:
            self._prepare(pool)

    # -- vectorised pool table ------------------------------------------------
    def _prepare(self, pool: list[Candidate]) -> None:
        import numpy as np

        n = len(pool)
        self.idx = {c.user_id: i for i, c in enumerate(pool)}
        lat = np.radians([c.location[0] for c in pool])
        lng = np.radians([c.location[1] for c in pool])
        clat, clng = np.radians(self.rules.campus[0]), np.radians(self.rules.campus[1])

        def hav(la1, lo1, la2, lo2):
            h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
            return 2 * 6371.0 * np.arcsin(np.sqrt(h))

        d = hav(lat[:, None], lng[:, None], lat[None, :], lng[None, :])
        to_c = hav(lat, lng, clat, clng)
        ac, bc = to_c[:, None], to_c[None, :]
        with np.errstate(divide="ignore", invalid="ignore"):
            via_b = np.where(ac > 0, (d + bc) / ac - 1, np.inf)
            via_a = np.where(bc > 0, (d + ac) / bc - 1, np.inf)
        det = np.maximum(0.0, np.minimum(via_b, via_a))
        route = np.maximum(0.0, 40 * (1 - det / 0.35))
        near = np.minimum(20.0, np.maximum(0.0, 20 * (1 - (d - 1.5) / 6.5)))

        on = np.zeros((n, len(DAYS)), bool)
        tin = np.zeros((n, len(DAYS)))
        tout = np.zeros((n, len(DAYS)))
        for i, c in enumerate(pool):
            for k, day in enumerate(DAYS):
                if day in c.schedule:
                    on[i, k] = True
                    tin[i, k] = minutes(c.schedule[day]["in"])
                    tout[i, k] = minutes(c.schedule[day]["out"])

        def slot(v):
            return np.where(v <= 15, 1.0, np.where(v <= 30, 0.5, 0.0))

        both = on[:, None, :] & on[None, :, :]
        ok = np.where(both, slot(np.abs(tin[:, None, :] - tin[None, :, :])) * 0.7
                      + slot(np.abs(tout[:, None, :] - tout[None, :, :])) * 0.3, 0.0)
        ndays = on.sum(axis=1)
        ssum = np.zeros((n, n))
        for k in range(len(DAYS)):  # sum in day order, as pair_fit does
            ssum = ssum + np.where(on[:, None, k], ok[:, :, k], 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            sched = np.where(ndays[:, None] > 0, 30 * ssum / ndays[:, None], 0.0)
        good = ((ok >= 0.7) & on[:, None, :]).any(axis=2)

        bit = {m: 1 << i for i, m in enumerate(METHODS)}
        mask = np.array([sum(bit[m] for m in c.methods if m in bit) for c in pool])
        pref = np.where((mask[:, None] & mask[None, :]) != 0, 10.0, 0.0)

        fem = np.array([c.gender == "female" for c in pool])
        wo = np.array([c.women_only for c in pool])
        allowed_m = ~((wo[:, None] & ~fem[None, :]) | (wo[None, :] & ~fem[:, None]))
        total = np.round(route + near + sched + pref)
        total = np.where(allowed_m, total, 0).astype(int)
        r = self.rules
        okm = allowed_m & good & good.T & (total >= r.pair_min) & (total.T >= r.pair_min)
        np.fill_diagonal(okm, False)
        for pair in r.excluded:
            ids = [self.idx.get(u) for u in pair]
            if len(ids) == 2 and None not in ids:
                okm[ids[0], ids[1]] = okm[ids[1], ids[0]] = False
        self.T, self.G, self.OK, self.D = total, good & allowed_m, okm, d
        for c in pool:
            self._arrivals(c)

    def _both(self, a: Candidate, b: Candidate):
        i, j = self.idx.get(a.user_id), self.idx.get(b.user_id)
        return (i, j) if i is not None and j is not None else None

    # -- queries ----------------------------------------------------------------
    def fit(self, a: Candidate, b: Candidate) -> PairFit | None:
        k = (a.user_id, b.user_id)
        if k not in self._fit:
            self._fit[k] = pair_fit(a, b, self.rules.campus)
        return self._fit[k]

    def total(self, a: Candidate, b: Candidate) -> int:
        ij = self._both(a, b)
        if ij:
            return int(self.T[ij])
        p = self.fit(a, b)
        return p.total if p else 0

    def candidate(self, a: Candidate, b: Candidate) -> bool:
        """b can be suggested to a: allowed, fit >= min_fit, and a good day in common."""
        if a.user_id == b.user_id or frozenset((a.user_id, b.user_id)) in self.rules.excluded:
            return False
        ij = self._both(a, b)
        if ij:
            return bool(self.G[ij]) and self.T[ij] >= self.rules.min_fit
        p = self.fit(a, b)
        return bool(p and p.total >= self.rules.min_fit and p.good_days)

    def ok(self, a: Candidate, b: Candidate) -> bool:
        ij = self._both(a, b)
        if ij:
            return bool(self.OK[ij])
        k = (a.user_id, b.user_id) if a.user_id < b.user_id else (b.user_id, a.user_id)
        if k not in self._ok:
            r = self.rules
            good = frozenset(k) not in r.excluded
            for x, y in ((a, b), (b, a)):
                if not good:
                    break
                p = self.fit(x, y)
                good = p is not None and p.total >= r.pair_min and bool(p.good_days)
            self._ok[k] = good
        return self._ok[k]

    def _arrivals(self, c: Candidate) -> dict[str, int]:
        if c.user_id not in self._arr:
            self._arr[c.user_id] = {d: minutes(c.schedule[d]["in"]) for d in DAYS if d in c.schedule}
        return self._arr[c.user_id]

    def group_days(self, group: list[Candidate]) -> list[str]:
        arr = [self._arrivals(c) for c in group]
        ref, w = arr[0], self.rules.window_min
        return [d for d in DAYS if all(d in a for a in arr) and all(abs(a[d] - ref[d]) <= w for a in arr)]

    def feasible(self, group: list[Candidate]) -> bool:
        r = self.rules
        if not 2 <= len(group) <= r.max_circle_size:
            return False
        if not all(self.ok(a, b) for a, b in combinations(group, 2)):
            return False
        if not (self.group_days(group) and travel_modes(group)):
            return False
        return self.detour_ok(group)

    def arrange(self, group: list[Candidate]) -> list[Candidate] | None:
        """The group with a valid founder first, or None if no member can found it.

        The timetable window is measured from the circle's first member (prototype rule),
        so feasibility can depend on who is first; a set of students is a valid circle if
        any of them can be its founder.
        """
        if self.feasible(group):
            return list(group)
        for i in range(1, len(group)):
            g = [group[i]] + group[:i] + group[i + 1:]
            if self.feasible(g):
                return g
        return None

    def rider_detour_min(self, group: list[Candidate]) -> dict[int, float]:
        key = frozenset(c.user_id for c in group)  # pickup order depends only on who is in it
        if key not in self._det:
            r = self.rules
            self._det[key] = rider_detours_min(group, r.campus, r.road_factor, r.speed_kmh)
        return self._det[key]

    def detour_ok(self, group: list[Candidate]) -> bool:
        lim = self.rules.max_detour_min
        return lim is None or max(self.rider_detour_min(group).values()) <= lim

    def circle_fit(self, group: list[Candidate]) -> int:
        """Average fit over every pair, in both directions (so it doesn't depend on who is
        listed first; the prototype averaged one direction per pair)."""
        scores = [self.total(a, b) + self.total(b, a) for a, b in combinations(group, 2)]
        return round(sum(scores) / (2 * len(scores))) if scores else 0


def pair_ok(a: Candidate, b: Candidate, rules: Rules) -> bool:
    return Scorer(rules).ok(a, b)


def feasible(group: list[Candidate], rules: Rules) -> bool:
    return Scorer(rules).feasible(group)


def circle_fit(group: list[Candidate], campus: tuple[float, float]) -> int:
    return Scorer(Rules(campus=campus)).circle_fit(group)


def fit_label(v: int) -> str:
    return "Great fit" if v >= 75 else "Good fit" if v >= 60 else "Fair fit"


def _route_seq(group: list[Candidate], campus: tuple[float, float]) -> list[Candidate]:
    order, _ = pickup_route_km([s.location for s in group], campus)  # furthest-first (prototype rule)
    return [group[i] for i in order]


def route_info(group: list[Candidate], campus: tuple[float, float], road_factor: float) -> dict:
    """Pickup order and road km of the whole trip (OSRM road distances where known)."""
    from . import roads

    seq = _route_seq(group, campus)
    pts = [s.location for s in seq] + [campus]
    km = sum(roads.km(pts[i], pts[i + 1], road_factor) for i in range(len(pts) - 1))
    return {"order": [s.user_id for s in seq], "road_km": km}


def _rider_extra(group, campus, leg) -> dict[int, float]:
    seq = _route_seq(group, campus)
    pts = [s.location for s in seq] + [campus]
    out = {}
    for k, s in enumerate(seq):
        ride = sum(leg(pts[j], pts[j + 1]) for j in range(k, len(pts) - 1))
        out[s.user_id] = max(0.0, ride - leg(s.location, campus))
    return out


def rider_detours_km(group: list[Candidate], campus: tuple[float, float], road_factor: float) -> dict[int, float]:
    """Extra road km each member rides compared with going straight to campus.

    Pickups run furthest-first (prototype rule), so the first person picked up rides
    past everyone else's pickup; the last rides almost directly.
    """
    from . import roads

    return _rider_extra(group, campus, lambda a, b: roads.km(a, b, road_factor))


def rider_detours_min(group: list[Candidate], campus: tuple[float, float], road_factor: float,
                      speed_kmh: float) -> dict[int, float]:
    """Extra minutes each member rides compared with going straight to campus (OSRM times x
    traffic factor where known; otherwise road km at ``speed_kmh``)."""
    from . import roads

    return _rider_extra(group, campus, lambda a, b: roads.minutes(a, b, road_factor, speed_kmh))


def capacity(mode: str, group: list[Candidate]) -> int:
    if mode == "Classmate drives":
        return max((s.seats + 1 for s in group if s.has_car), default=len(group))
    return MODE_CAPACITY.get(mode, 4)
