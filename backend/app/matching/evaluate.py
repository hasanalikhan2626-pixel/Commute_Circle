"""Metrics used to compare algorithms (Research Question 2 in the proposal)."""
from __future__ import annotations

from .compat import Rules, best_detour, group_days
from .geo import haversine_km
from .types import Candidate, MatchResult


def evaluate(result: MatchResult, pool: list[Candidate], rules: Rules, *, road_factor: float = 1.3,
             km_per_litre: float = 12.0, fuel_price: float = 265.0, co2_per_litre: float = 2.31) -> dict:
    by_id = {c.user_id: c for c in pool}
    matched = sum(len(c.member_ids) for c in result.circles)
    sizes = [len(c.member_ids) for c in result.circles]
    detours, shared, solo_km, pooled_km = [], [], 0.0, 0.0
    for circ in result.circles:
        group = [by_id[i] for i in circ.member_ids]
        d = best_detour(group, rules)
        detours.append(d)
        days = len(group_days(group, rules.window_min))
        shared.append(days)
        # Per shared day, round trip: everyone driving alone vs one car with detour.
        alone = sum(haversine_km(m.location, rules.campus) for m in group)
        driver_direct = min(haversine_km(m.location, rules.campus) for m in group if m.has_car)
        solo_km += 2 * alone * road_factor * days
        pooled_km += 2 * (driver_direct + d) * road_factor * days
    saved_km_week = max(0.0, solo_km - pooled_km)
    litres = saved_km_week / km_per_litre
    n = len(pool)
    avg = lambda xs: round(sum(xs) / len(xs), 3) if xs else 0.0  # noqa: E731
    return {
        "algorithm": result.algorithm,
        "pool_size": n,
        "circles": len(result.circles),
        "matched": matched,
        "match_rate": round(matched / n, 4) if n else 0.0,
        "avg_circle_size": avg(sizes),
        "avg_score": avg([c.score for c in result.circles]),
        "avg_detour_km": avg(detours),
        "avg_shared_days": avg(shared),
        "weekly_km_saved": round(saved_km_week, 1),
        "weekly_fuel_pkr_saved": round(litres * fuel_price),
        "weekly_co2_kg_saved": round(litres * co2_per_litre, 1),
        "runtime_ms": result.runtime_ms,
    }
