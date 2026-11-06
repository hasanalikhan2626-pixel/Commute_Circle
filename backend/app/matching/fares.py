"""Fare model: rupees per road km for each way of travelling (prototype rates).

Ride-hailing and rickshaw are a fare split between the group. "Classmate drives"
shares the driver's fuel. Family driver and parent drop cost the circle nothing.
"""
from __future__ import annotations

from .geo import haversine_km

RATE_PER_KM = {"Shared ride-hailing": 52.0, "Rickshaw": 38.0, "Family driver": 0.0, "Parent drop": 0.0}


def rate(mode: str, fuel_price: float, km_per_litre: float) -> float:
    if mode == "Classmate drives":
        return fuel_price / km_per_litre
    return RATE_PER_KM.get(mode, RATE_PER_KM["Shared ride-hailing"])


def solo_fare(location, campus, mode: str, road_factor: float, fuel_price: float, km_per_litre: float) -> float:
    """What one trip to campus would cost travelling alone the same way."""
    return haversine_km(location, campus) * road_factor * rate(mode, fuel_price, km_per_litre)
