"""Metrics used to compare algorithms (Research Question 2)."""
from __future__ import annotations

from .compat import Rules, capacity, group_days, rider_detours_min, route_info
from . import roads
from .fares import PASSENGER_PAYS, rate, solo_fare
from .geo import haversine_km
from .types import Candidate, MatchResult


def evaluate(result: MatchResult, pool: list[Candidate], rules: Rules, *, road_factor: float = 1.35,
             fuel_price: float = 352.59, km_per_litre: float = 12.0, co2_per_litre: float = 2.31,
             speed_kmh: float = 22.0, detour_limit_min: float = 12.0) -> dict:
    """Metrics for one matching result.

    Detour minutes = extra road km per rider / ``speed_kmh`` (an assumed average city
    speed, configurable; replace with routing-API times when available).
    """
    by_id = {c.user_id: c for c in pool}
    matched = sum(len(c.member_ids) for c in result.circles)
    sizes, detours, shared, saved, car_km_saved = [], [], [], 0.0, 0.0
    rider_min, occupancy = [], []
    for circ in result.circles:
        g = [by_id[i] for i in circ.member_ids]
        sizes.append(len(g))
        days = len(group_days(g, rules.window_min))
        shared.append(days)
        info = route_info(g, rules.campus, road_factor)
        first = by_id[info["order"][0]]
        detours.append(max(0.0, info["road_km"] - roads.km(first.location, rules.campus, road_factor)))
        rider_min += list(rider_detours_min(g, rules.campus, road_factor, speed_kmh).values())
        occupancy.append(len(g) / capacity(circ.mode, g))
        trip = info["road_km"] * rate(circ.mode, fuel_price, km_per_litre)
        solos = {s.user_id: solo_fare(s.location, rules.campus, circ.mode, road_factor, fuel_price, km_per_litre) for s in g}
        if circ.mode in PASSENGER_PAYS:
            # the provider travels anyway (own bike, or the family's own car): not a saving.
            prov = next((s.user_id for s in g if s.has_bike), None) if circ.mode == "Motorbike pillion" else None
            solos.pop(prov if prov is not None else min(solos, key=solos.get), None)
        alone = sum(solos.values())
        saved += max(0.0, alone - trip) * days
        solo_km = sum(roads.km(s.location, rules.campus, road_factor) for s in g)
        car_km_saved += max(0.0, solo_km - info["road_km"]) * days
    from .optimise import Valuer
    from .compat import Scorer

    groups = [[by_id[i] for i in c.member_ids] for c in result.circles]
    objective = Valuer(Scorer(rules, [c for g in groups for c in g] or None)).total(groups)
    n = len(pool)
    avg = lambda xs: round(sum(xs) / len(xs), 3) if xs else 0.0  # noqa: E731
    return {
        "algorithm": result.algorithm,
        "pool_size": n,
        "circles": len(result.circles),
        "matched": matched,
        "match_rate": round(matched / n, 4) if n else 0.0,
        "avg_circle_size": avg(sizes),
        "avg_fit": avg([c.fit for c in result.circles]),
        "avg_detour_km": avg(detours),
        "avg_rider_detour_min": avg(rider_min),
        "max_rider_detour_min": round(max(rider_min), 1) if rider_min else 0.0,
        "riders_within_limit": round(sum(m <= detour_limit_min for m in rider_min) / len(rider_min), 4) if rider_min else 0.0,
        "occupancy": avg(occupancy),
        "avg_shared_days": avg(shared),
        "weekly_pkr_saved": round(saved),  # trips to campus, vs each member travelling alone the same way
        "weekly_vehicle_km_saved": round(car_km_saved, 1),
        "weekly_co2_kg_saved": round(car_km_saved / km_per_litre * co2_per_litre, 1),
        "objective": round(objective, 1),
        "runtime_ms": result.runtime_ms,
    }
