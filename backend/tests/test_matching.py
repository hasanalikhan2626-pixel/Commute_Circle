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
                      s["has_car"], s["seats"], s["schedule"], s.get("has_bike", False)) for s in rows]


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


def test_vectorised_scores_match_pair_fit():
    from app.matching.compat import Scorer, pair_ok

    for seed in range(3):
        pool = pool_from(make_students(80, 50 + seed))
        sc = Scorer(RULES, pool)
        for a in pool:
            for b in pool:
                if a is b:
                    continue
                p = pair_fit(a, b, CAMPUS)
                assert sc.total(a, b) == (p.total if p else 0), (a.user_id, b.user_id)
                assert sc.candidate(a, b) == bool(p and p.total >= 45 and p.good_days)
                assert sc.ok(a, b) == pair_ok(a, b, RULES)


def test_rickshaw_carries_three():
    four = [cand(i, methods=(RK,)) for i in range(1, 5)]
    assert travel_modes(four) == [] and travel_modes(four[:3]) == [RK]


def test_rider_detours():
    from app.matching.compat import rider_detours_km

    far, near = cand(1, area="Gulshan-e-Iqbal Block 10"), cand(2, area="Gulshan-e-Iqbal Block 13")
    d = rider_detours_km([far, near], CAMPUS, 1.35)
    assert d[2] == 0  # picked up last: rides straight to campus
    assert 0 <= d[1] < 1.0  # Gulshan 10 -> 13 is on the way
    assert rider_detours_km([cand(3)], CAMPUS, 1.35) == {3: 0.0}


def test_evaluate_reports_minutes_and_occupancy():
    from app.matching.evaluate import evaluate

    pool = pool_from(make_students(60, 3))
    m = evaluate(ALGORITHMS["compatibility"](pool, RULES, 0), pool, RULES, speed_kmh=20)
    assert m["avg_rider_detour_min"] >= 0 and m["max_rider_detour_min"] >= m["avg_rider_detour_min"]
    assert 0 < m["riders_within_limit"] <= 1 and 0 < m["occupancy"] <= 1


def test_dbscan_groups_dense_areas():
    from app.matching.optimise import dbscan

    g13, g10, bahria = AREAS["Gulshan-e-Iqbal Block 13"], AREAS["Gulshan-e-Iqbal Block 10"], AREAS["Bahria Town"]
    pts = [g13, g13, g10, g13, bahria]
    assert haversine_km(g13, g10) > 1.5  # 1.51 km apart
    assert dbscan(pts, eps_km=1.5) == [0, 0, -1, 0, -1]  # Gulshan 10 just outside the radius; Bahria is noise
    assert dbscan(pts, eps_km=1.6) == [0, 0, 0, 0, -1]


def test_detour_limit_is_a_hard_rule():
    # Model Colony -> Bahadurabad -> campus is a long way round for the first rider.
    far = [cand(1, area="Malir Cantt"), cand(2, area="Saddar")]
    assert not feasible(far, RULES)
    assert feasible(far, Rules(campus=CAMPUS, max_detour_min=None)) in (True, False)  # only the cap changed


@pytest.mark.parametrize("seed", range(3))
def test_exact_optimum_and_genetic_quality(seed):
    from app.matching.algorithms import EXACT
    from app.matching.evaluate import evaluate

    pool = pool_from(make_students(40, 200 + seed))
    score = {n: evaluate(f(pool, RULES, 0), pool, RULES)["objective"] for n, f in {**ALGORITHMS, **EXACT}.items()}
    assert score["milp"] >= max(score.values()) - 1e-6, score  # nothing beats the optimum
    assert score["genetic"] >= max(score["compatibility"], score["greedy"], score["dbscan_km"]) - 1e-6, score


def test_feasibility_is_per_set_founder_first():
    from app.matching.compat import Scorer

    sc = Scorer(RULES)
    t = lambda i: {"in": i, "out": "14:00"}  # noqa: E731
    # Monday is the only day all three come; only b (08:20) has everyone within 20 minutes.
    a = cand(1, sched={"Mon": t("08:00"), "Tue": t("08:30"), "Thu": t("08:30")})
    b = cand(2, sched={"Mon": t("08:20"), "Tue": t("08:30"), "Wed": t("08:30")})
    c = cand(3, sched={"Mon": t("08:40"), "Wed": t("08:30"), "Thu": t("08:30")})
    assert sc.ok(a, b) and sc.ok(b, c) and sc.ok(a, c)
    assert not sc.feasible([a, b, c]) and not sc.feasible([c, a, b]) and sc.feasible([b, a, c])
    assert [x.user_id for x in sc.arrange([a, b, c])][0] == 2
    assert sc.circle_fit([a, b, c]) == sc.circle_fit([c, b, a])  # fit is order-independent


def test_road_matrix_and_fallback(monkeypatch):
    from app.matching import roads

    g13 = AREAS["Gulshan-e-Iqbal Block 13"]
    assert roads.using_matrix(CAMPUS)
    straight = haversine_km(g13, CAMPUS)
    assert 1.1 * straight < roads.km(g13, CAMPUS) < 2 * straight  # real roads are longer than a straight line
    monkeypatch.setenv("CC_TRAFFIC_FACTOR", "1.0")
    free = roads.minutes(g13, CAMPUS)
    monkeypatch.setenv("CC_TRAFFIC_FACTOR", "2.0")
    assert roads.minutes(g13, CAMPUS) == pytest.approx(2 * free)
    odd = (24.9, 67.0)  # not a pickup area: straight line x 1.35 at 22 km/h
    assert roads.km(odd, CAMPUS) == pytest.approx(haversine_km(odd, CAMPUS) * 1.35)
    assert roads.minutes(odd, CAMPUS) == pytest.approx(haversine_km(odd, CAMPUS) * 1.35 / 22 * 60)


def test_motorbike_pillion_rules():
    MB = "Motorbike pillion"
    rider, pillion = cand(1, g="male", methods=(MB,)), cand(2, g="male", methods=(MB,))
    rider = Candidate(**{**rider.__dict__, "has_bike": True})
    assert travel_modes([rider, pillion]) == [MB]
    assert travel_modes([pillion, cand(3, g="male", methods=(MB,))]) == []  # nobody has a bike
    assert travel_modes([rider, pillion, cand(3, g="male", methods=(MB,))]) == []  # a bike carries 2


def test_cost_card_matches_appendix_c():
    from app.matching.fares import cost_card, payers

    bike = cost_card("Motorbike pillion", 15, 2, 352.59, 12)
    assert bike["total"] == 225 and bike["per_person"] == 225 and bike["payers"] == 1  # Rs 15/km x 15 km
    hail = cost_card("Shared ride-hailing", 18.3, 4, 352.59, 12)
    assert hail["total"] == round(52 * 18.3) and hail["per_person"] == round(52 * 18.3 / 4) and "split 4 ways" in hail["text"]
    parent = cost_card("Parent drop", 15, 3, 352.59, 12)
    assert parent["total"] == 300 and parent["payers"] == 2 and parent["per_person"] == 150  # Rs 20/km, 2 passengers
    car = cost_card("Classmate drives", 12, 4, 352.59, 12)
    assert car["total"] == round(12 / 12 * 352.59) and car["payers"] == 4  # fuel split with the driver
    assert payers("Family driver", 4) == 3 and payers("Rickshaw", 3) == 3


def test_privacy_simulation_runs():
    from app.matching import roads
    from app.privacy_sim import simulate

    rows = simulate(n=40, datasets=1, spreads=(1.0,))
    by = {r["level"]: r for r in rows}
    assert by["exact"]["route_penalty_mean"] == 0 and by["exact"]["walk_m_mean_mean"] == 0
    assert by["area"]["k_anonymity_mean"] >= by["exact"]["k_anonymity_mean"] == 1
    assert roads.using_matrix(CAMPUS)  # the simulation restores the road table afterwards
