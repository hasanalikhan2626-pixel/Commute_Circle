"""Fare model (proposal Appendix C): rupees per road km and who pays.

* Shared ride-hailing (Rs 52/km) and auto-rickshaw (Rs 38/km): the fare is split equally
  between everyone who travels.
* Classmate drives: the fuel (road km / 12 km/L x petrol price) is split equally between
  everyone, driver included.
* Motorbike pillion: the passenger pays the rider a flat Rs 15/km.
* Family driver / parent drop: passengers pay a fuel contribution of Rs 20/km, shared
  between them; the host family pays nothing.
"""
from __future__ import annotations

from . import roads

RATE_PER_KM = {"Shared ride-hailing": 52.0, "Rickshaw": 38.0, "Motorbike pillion": 15.0,
               "Family driver": 20.0, "Parent drop": 20.0}
# What one student pays travelling alone the same kind of way.
SOLO_RATE = {"Motorbike pillion": 50.0}  # bike ride-hailing (proposal Appendix C: Rs 750 for 15 km)
PASSENGER_PAYS = ("Motorbike pillion", "Family driver", "Parent drop")  # the provider is not charged


def rate(mode: str, fuel_price: float, km_per_litre: float) -> float:
    if mode == "Classmate drives":
        return fuel_price / km_per_litre
    return RATE_PER_KM.get(mode, RATE_PER_KM["Shared ride-hailing"])


def solo_rate(mode: str, fuel_price: float, km_per_litre: float) -> float:
    return SOLO_RATE.get(mode, rate(mode, fuel_price, km_per_litre))


def solo_fare(location, campus, mode: str, road_factor: float, fuel_price: float, km_per_litre: float) -> float:
    """What one trip to campus would cost this student travelling alone the same way."""
    return roads.km(location, campus, road_factor) * solo_rate(mode, fuel_price, km_per_litre)


def payers(mode: str, size: int) -> int:
    """How many people share the cost of one trip."""
    return max(1, size - 1) if mode in PASSENGER_PAYS else size


def cost_card(mode: str, road_km: float, size: int, fuel_price: float, km_per_litre: float) -> dict:
    """Explainable cost breakdown for one trip to campus (proposal section 14.9)."""
    r = rate(mode, fuel_price, km_per_litre)
    km = round(road_km, 1)
    n = payers(mode, size)
    if mode == "Motorbike pillion":
        total = r * road_km
        text = f"Flat tariff Rs {r:g}/km x {km} km = Rs {total:,.0f}, paid by the passenger to the rider."
    elif mode in ("Family driver", "Parent drop"):
        total = r * road_km
        text = (f"Fuel contribution Rs {r:g}/km x {km} km = Rs {total:,.0f}, shared by {n} passenger"
                f"{'s' if n > 1 else ''} = Rs {total / n:,.0f} each. The host family pays nothing.")
    elif mode == "Classmate drives":
        litres = road_km / km_per_litre
        total = litres * fuel_price
        text = (f"Fuel: {km} km / {km_per_litre:g} km per litre = {litres:.1f} L x Rs {fuel_price:g} = "
                f"Rs {total:,.0f}, split {n} ways (driver included) = Rs {total / n:,.0f} each.")
    else:
        total = r * road_km
        what = "Shared ride-hailing fare" if mode == "Shared ride-hailing" else "Rickshaw fare"
        text = (f"{what} about Rs {r:g}/km x {km} km = Rs {total:,.0f}, split {n} ways = "
                f"Rs {total / n:,.0f} each.")
    return {"mode": mode, "road_km": km, "rate_per_km": round(r, 2), "total": round(total),
            "payers": n, "per_person": round(total / n), "text": text}
