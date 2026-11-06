"""Unit tests for the matching engine: every algorithm must respect every hard constraint."""
import random

import pytest

from app.areas import AREAS
from app.matching.algorithms import ALGORITHMS
from app.matching.compat import Rules, capacity, feasible, gender_ok, group_days
from app.matching.geo import detour_km, haversine_km
from app.matching.types import Candidate

CAMPUS = (24.8607, 67.07)
RULES = Rules(campus=CAMPUS)
WEEK = {d: {"arrive": "08:30", "leave": "14:00"} for d in ("mon", "tue", "wed")}


def cand(uid, area="PECHS", car=False, seats=0, gender="male", sgo=False, sched=None):
    return Candidate(uid, AREAS[area], gender, sgo, car, seats if car else 0, sched or WEEK)


def random_pool(n, seed):
    rng = random.Random(seed)
    areas = sorted(AREAS)
    pool = []
    for i in range(n):
        days = rng.sample(["mon", "tue", "wed", "thu", "fri"], rng.randint(2, 5))
        arrive = rng.choice(["08:00", "08:30", "09:00", "10:00"])
        car = rng.random() < 0.35
        g = rng.choice(["male", "female"])
        pool.append(Candidate(i + 1, AREAS[rng.choice(areas[:10])], g, g == "female" and rng.random() < 0.4,
                              car, rng.randint(1, 4) if car else 0,
                              {d: {"arrive": arrive, "leave": "15:00"} for d in days}))
    return pool


def test_haversine_known_distance():
    # Clifton to Gulshan is roughly 14 km in a straight line.
    assert 12 < haversine_km(AREAS["Clifton"], AREAS["Gulshan-e-Iqbal"]) < 16


def test_detour_zero_when_no_pickups():
    assert detour_km(AREAS["Clifton"], [], CAMPUS) == 0


def test_group_days_respects_window():
    a = cand(1, sched={"mon": {"arrive": "08:00", "leave": "12:00"}, "tue": {"arrive": "08:00", "leave": "12:00"}})
    b = cand(2, sched={"mon": {"arrive": "08:30", "leave": "12:00"}, "tue": {"arrive": "08:45", "leave": "12:00"}})
    assert group_days([a, b], 30) == ["mon"]


def test_gender_preference():
    f1 = cand(1, gender="female", sgo=True)
    assert gender_ok([f1, cand(2, gender="female")])
    assert not gender_ok([f1, cand(3, gender="male")])
    assert gender_ok([cand(4), cand(5, gender="female")])


def test_needs_a_driver_and_seats():
    assert not feasible([cand(1), cand(2)], RULES)
    assert feasible([cand(1, car=True, seats=1), cand(2)], RULES)
    assert not feasible([cand(1, car=True, seats=1), cand(2), cand(3)], RULES)
    assert capacity([cand(1, car=True, seats=3)]) == 4


def test_excluded_pair_never_feasible():
    rules = Rules(campus=CAMPUS, excluded=frozenset({frozenset((1, 2))}))
    assert not feasible([cand(1, car=True, seats=3), cand(2)], rules)


def test_far_rider_rejected_by_detour_limit():
    assert not feasible([cand(1, "Clifton", car=True, seats=3), cand(2, "Bahria Town")], RULES)


@pytest.mark.parametrize("name", list(ALGORITHMS))
@pytest.mark.parametrize("seed", range(5))
def test_algorithms_respect_constraints(name, seed):
    pool = random_pool(50, seed)
    by_id = {c.user_id: c for c in pool}
    result = ALGORITHMS[name](pool, RULES, seed)
    seen = set()
    for circle in result.circles:
        group = [by_id[i] for i in circle.member_ids]
        assert feasible(group, RULES), circle
        assert not seen & set(circle.member_ids), "student placed in two circles"
        seen |= set(circle.member_ids)
        assert set(circle.driver_ids) == {c.user_id for c in group if c.has_car}
    assert seen | set(result.unmatched) == set(by_id)
    assert not seen & set(result.unmatched)


@pytest.mark.parametrize("name", list(ALGORITHMS))
def test_algorithms_deterministic(name):
    pool = random_pool(40, 7)
    a, b = ALGORITHMS[name](pool, RULES, 3), ALGORITHMS[name](pool, RULES, 3)
    assert [c.member_ids for c in a.circles] == [c.member_ids for c in b.circles]


@pytest.mark.parametrize("name", list(ALGORITHMS))
def test_algorithms_handle_tiny_pools(name):
    assert ALGORITHMS[name]([], RULES, 0).circles == []
    assert ALGORITHMS[name]([cand(1, car=True, seats=2)], RULES, 0).unmatched == [1]


def test_compatibility_places_obvious_pair():
    pool = [cand(1, car=True, seats=3), cand(2), cand(3)]
    r = ALGORITHMS["compatibility"](pool, RULES, 0)
    assert len(r.circles) == 1 and sorted(r.circles[0].member_ids) == [1, 2, 3]
