"""Fuel cost split and savings estimate for a circle."""
from __future__ import annotations

from ..config import settings
from ..matching.compat import best_detour, group_days
from ..matching.geo import haversine_km
from .candidates import rules_for, to_candidate

WEEKS_PER_MONTH = 4.33


def circle_costs(db, profiles) -> dict:
    rules = rules_for(db)
    group = [to_candidate(p) for p in profiles]
    if not any(c.has_car for c in group) or len(group) < 2:
        return {"available": False}
    days = len(group_days(group, settings.schedule_window_min))
    detour = best_detour(group, rules)
    drivers = [c for c in group if c.has_car]
    car_km = (min(haversine_km(d.location, rules.campus) for d in drivers) + detour) * settings.road_factor
    trip_cost = car_km / settings.fuel_km_per_litre * settings.fuel_price_pkr
    trips_month = days * 2 * WEEKS_PER_MONTH
    share = trip_cost / len(group)
    per_member = []
    for c in group:
        solo_km = haversine_km(c.location, rules.campus) * settings.road_factor
        solo_trip = solo_km / settings.fuel_km_per_litre * settings.fuel_price_pkr
        per_member.append({
            "user_id": c.user_id,
            "solo_monthly_pkr": round(solo_trip * trips_month),
            "shared_monthly_pkr": round(share * trips_month),
            "saving_pct": round(100 * (1 - share / solo_trip), 1) if solo_trip else 0.0,
        })
    return {
        "available": True,
        "shared_days_per_week": days,
        "trip_km": round(car_km, 1),
        "trip_cost_pkr": round(trip_cost),
        "share_per_trip_pkr": round(share),
        "monthly_share_pkr": round(share * trips_month),
        "fuel_price_pkr": settings.fuel_price_pkr,
        "per_member": per_member,
        "assumptions": (
            f"Petrol PKR {settings.fuel_price_pkr:g}/L, {settings.fuel_km_per_litre:g} km/L, "
            f"road distance = {settings.road_factor:g}x straight line, {WEEKS_PER_MONTH} weeks/month, "
            "round trip each shared day, cost split equally."
        ),
    }
