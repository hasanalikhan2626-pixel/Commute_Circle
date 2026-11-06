"""Matching engine: the prototype's fit score, hard rules, and every algorithm respecting them."""
import pytest

from app.areas import AREAS
from app.benchmark import prototype_pool
from app.matching.algorithms import ALGORITHMS, build_for, options_for
from app.matching.compat import Rules, allowed, circle_fit, feasible, group_days, pair_fit, travel_modes
from app.matching.geo import detour_ratio, haversine_km
from app.matching.types import Candidate
from app.seed import make_students

CAMPUS = (24.8086702, 67.1217257)
RULES = Rules(campus=CAMPUS)
WEEK = {d: {"in": "08:30", "out": "14:00"} for d in ("Mon", "Tue", "Wed", "Thu", "Fri")}
SH, CD, RK = "Shared ride-hailing", "Classmate drives", "Rickshaw"


def cand(uid, area="Gulshan-e-Iqbal Block 13", g="female", wo=False, methods=(SH,), car=False, seats=0, sched=None):
    return Candidate(uid, AREAS[area], g, wo, tuple(methods), car, seats, sched or WEEK)


def pool_from(rows):
    return [Candidate(s["user_id"], AREAS[s["area"]], s["gender"], s["women_only"], tuple(s["methods"]),
                      s["has_car"], s["seats"], s["schedule"]) for s in rows]


def test_same_area_same_times_is_a_great_fit():
    p = pair_fit(cand(1), cand(2), CAMPUS)
    assert p.total == 100 and p.route == 40 and p.near == 20 and p.sched == 30 and p.pref == 10
    assert p.on_way and len(p.good_days) == 5


def test_fit_components_fall_off():
    far = pair_fit(cand(1), cand(2, area="Clifton Block 5"), CAMPUS)
    assert far.near == 0 and far.route < 40
    late = pair_fit(cand(1), cand(2, sched={d: {"in": "09:15", "out": "14:00"} for d in WEEK}), CAMPUS)
    assert late.sched == 9 and not late.good_days  # 45 min later: arrival 0, leaving 0.3
    assert pair_fit(cand(1), cand(2, methods=(RK,)), CAMPUS).pref == 0


def test_women_only():
    w = cand(1, wo=True)
    assert allowed(w, cand(2)) and not allowed(w, cand(3, g="male")) and allowed(cand(4, g="male"), cand(5))
    assert pair_fit(w, cand(3, g="male"), CAMPUS) is None


def test_detour_ratio_on_the_way():
    # Gulshan 10 -> Gulshan 13 -> campus is nearly on the way.
    assert detour_ratio(AREAS["Gulshan-e-Iqbal Block 10"], AREAS["Gulshan-e-Iqbal Block 13"], CAMPUS) < 0.12
    assert 12 < haversine_km(AREAS["Clifton Block 5"], AREAS["Gulshan-e-Iqbal Block 13"]) < 16


def test_group_days_window_from_first_member():
    a = cand(1)
    b = cand(2, sched={"Mon": {"in": "08:45", "out": "14:00"}, "Tue": {"in": "09:00", "out": "14:00"}})
    assert group_days([a, b], 20) == ["Mon"]


def test_travel_modes_need_agreement_and_a_car_for_classmate_drives():
    assert travel_modes([cand(1, methods=(SH, CD)), cand(2, methods=(CD,))]) == []
    assert travel_modes([cand(1, methods=(SH, CD), car=True, seats=1), cand(2, methods=(CD,))]) == [CD]
    three = [cand(1, methods=(CD,), car=True, seats=1), cand(2, methods=(CD,)), cand(3, methods=(CD,))]
    assert travel_modes(three) == []  # one seat is not enough for three


def test_feasibility_rules():
    assert feasible([cand(1), cand(2)], RULES)
    assert not feasible([cand(1)], RULES)
    assert not feasible([cand(i) for i in range(5)], RULES)  # max 4
    assert not feasible([cand(1), cand(2, methods=(RK,))], RULES)  # no common way to travel
    assert not feasible([cand(1), cand(2, area="Clifton Block 5", sched={"Sat": {"in": "08:30", "out": "14:00"}})], RULES)
    excl = Rules(campus=CAMPUS, excluded=frozenset({frozenset((1, 2))}))
    assert not feasible([cand(1), cand(2)], excl)


def test_build_for_and_options():
    pool = [cand(1), cand(2), cand(3, area="Gulshan-e-Iqbal Block 10"), cand(4), cand(5, area="Clifton Block 5")]
    g = build_for(pool[0], pool, RULES)
    assert [c.user_id for c in g][0] == 1 and len(g) == 4 and 5 not in [c.user_id for c in g]
    opts = options_for(pool[0], pool, RULES)
    assert 1 <= len(opts) <= 3 and all(feasible(o, RULES) and o[0].user_id == 1 for o in opts)
    assert len({frozenset(c.user_id for c in o) for o in opts}) == len(opts)


def test_no_options_for_lonely_student():
    # The prototype's "no match" case: afternoon classes nobody else shares.
    late = cand(1, sched={d: {"in": "13:00", "out": "18:00"} for d in ("Mon", "Wed", "Fri")})
    assert options_for(late, [late, cand(2), cand(3)], RULES) == []


@pytest.mark.parametrize("name", list(ALGORITHMS))
@pytest.mark.parametrize("seed", range(4))
def test_algorithms_respect_rules(name, seed):
    pool = pool_from(make_students(60, seed))
    by_id = {c.user_id: c for c in pool}
    res = ALGORITHMS[name](pool, RULES, seed)
    seen = set()
    for circ in res.circles:
        grp = [by_id[i] for i in circ.member_ids]
        assert feasible(grp, RULES), circ
        assert circ.mode in travel_modes(grp)
        assert circ.fit == circle_fit(grp, CAMPUS)
        assert not seen & set(circ.member_ids)
        seen |= set(circ.member_ids)
    assert seen | set(res.unmatched) == set(by_id) and not seen & set(res.unmatched)


@pytest.mark.parametrize("name", list(ALGORITHMS))
def test_algorithms_deterministic_and_handle_tiny_pools(name):
    pool = pool_from(make_students(40, 7))
    a, b = ALGORITHMS[name](pool, RULES, 3), ALGORITHMS[name](pool, RULES, 3)
    assert [c.member_ids for c in a.circles] == [c.member_ids for c in b.circles]
    assert ALGORITHMS[name]([], RULES, 0).circles == []
    assert ALGORITHMS[name]([cand(1)], RULES, 0).unmatched == [1]


def test_prototype_students_mostly_matched():
    pool = prototype_pool()
    res = ALGORITHMS["compatibility"](pool, RULES, 0)
    assert sum(len(c.member_ids) for c in res.circles) / len(pool) > 0.8
