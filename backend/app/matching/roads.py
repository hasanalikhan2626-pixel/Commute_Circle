"""Road distances and travel times between pickup areas and campus.

Uses the OSRM table in ``app/data/road_matrix.json`` (OpenStreetMap road network) when both
points are known pickup areas or the campus; otherwise falls back to straight-line distance
x ``road_factor`` at ``fallback_speed_kmh``. OSRM times are free-flow, so they are multiplied
by ``traffic_factor`` (CC_TRAFFIC_FACTOR, default 2.0, i.e. about 25 km/h door to door at
peak times in Karachi).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from .geo import haversine_km

MATRIX = Path(__file__).resolve().parent.parent / "data" / "road_matrix.json"


def _key(p) -> tuple[float, float]:
    return (round(p[0], 6), round(p[1], 6))


@lru_cache(maxsize=1)
def _table():
    if os.environ.get("CC_ROAD_MATRIX", "on").lower() == "off" or not MATRIX.exists():
        return None
    from ..areas import AREAS

    d = json.loads(MATRIX.read_text())
    idx = {}
    for i, name in enumerate(d["names"]):
        if name == "__campus__":
            idx[_key(d["campus"])] = i
        elif name in AREAS:
            idx[_key(AREAS[name])] = i
    return idx, d["km"], d["minutes"], _key(d["campus"])


def traffic_factor() -> float:
    return float(os.environ.get("CC_TRAFFIC_FACTOR", "2.0"))


@lru_cache(maxsize=100_000)
def _lookup(a: tuple[float, float], b: tuple[float, float], which: int):
    t = _table()
    if t is None:
        return None
    i, j = t[0].get(_key(a)), t[0].get(_key(b))
    return None if i is None or j is None else t[1 + which][i][j]


def using_matrix(campus) -> bool:
    t = _table()
    return t is not None and t[3] == _key(campus)


def km(a, b, road_factor: float = 1.35) -> float:
    if a == b:
        return 0.0
    v = _lookup(a, b, 0)
    return v if v is not None else haversine_km(a, b) * road_factor


def minutes(a, b, road_factor: float = 1.35, fallback_speed_kmh: float = 22.0) -> float:
    if a == b:
        return 0.0
    v = _lookup(a, b, 1)
    if v is not None:
        return v * traffic_factor()
    return haversine_km(a, b) * road_factor / fallback_speed_kmh * 60
