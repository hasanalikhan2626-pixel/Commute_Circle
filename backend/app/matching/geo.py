from __future__ import annotations

import math


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lng1 = map(math.radians, a)
    lat2, lng2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def detour_ratio(a: tuple[float, float], b: tuple[float, float], campus: tuple[float, float]) -> float:
    """Extra distance (as a fraction) if one student collects the other on the way to
    campus, in the better of the two orders. 0 = exactly on the way."""
    ac, bc, ab = haversine_km(a, campus), haversine_km(b, campus), haversine_km(a, b)
    via_b = (ab + bc) / ac - 1 if ac else float("inf")
    via_a = (ab + ac) / bc - 1 if bc else float("inf")
    return max(0.0, min(via_b, via_a))


def pickup_route_km(points: list[tuple[float, float]], campus: tuple[float, float]) -> tuple[list[int], float]:
    """Furthest-from-campus first, then nearer pickups, then campus (prototype rule).
    Returns the pickup order (indexes into ``points``) and straight-line km."""
    order = sorted(range(len(points)), key=lambda i: -haversine_km(points[i], campus))
    dist = sum(haversine_km(points[order[i]], points[order[i + 1]]) for i in range(len(order) - 1))
    return order, dist + (haversine_km(points[order[-1]], campus) if order else 0.0)
