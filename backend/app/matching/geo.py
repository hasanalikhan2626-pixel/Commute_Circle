from __future__ import annotations

import math


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lng1 = map(math.radians, a)
    lat2, lng2 = map(math.radians, b)
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def detour_km(driver: tuple[float, float], pickups: list[tuple[float, float]], campus: tuple[float, float]) -> float:
    """Extra straight-line distance the driver travels to collect everyone.

    Pickups are visited greedily by nearest-next, which is close to optimal for
    the at-most-4 stops a circle can have.
    """
    direct = haversine_km(driver, campus)
    pos, remaining, total = driver, list(pickups), 0.0
    while remaining:
        nxt = min(remaining, key=lambda p: haversine_km(pos, p))
        total += haversine_km(pos, nxt)
        pos = nxt
        remaining.remove(nxt)
    total += haversine_km(pos, campus)
    return max(0.0, total - direct)
