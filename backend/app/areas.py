"""Karachi residential areas used as privacy-preserving pickup zones.

Students choose an area, never an exact address. Coordinates are approximate
area centroids (good to roughly 1 km), which is enough for grouping and
cost estimates and keeps home locations private.
"""
from __future__ import annotations

AREAS: dict[str, tuple[float, float]] = {
    "Bahadurabad": (24.8826, 67.0700),
    "Bahria Town": (25.0100, 67.3100),
    "Clifton": (24.8138, 67.0300),
    "DHA Phase 2": (24.8350, 67.0500),
    "DHA Phase 5": (24.8050, 67.0550),
    "DHA Phase 6": (24.7950, 67.0650),
    "DHA Phase 8": (24.7850, 67.0900),
    "Federal B Area": (24.9300, 67.0750),
    "Gulberg": (24.9330, 67.0700),
    "Gulistan-e-Johar": (24.9180, 67.1300),
    "Gulshan-e-Iqbal": (24.9215, 67.0947),
    "Kemari": (24.8200, 66.9800),
    "Korangi": (24.8300, 67.1300),
    "Malir": (24.8930, 67.2000),
    "Nazimabad": (24.9130, 67.0300),
    "North Karachi": (24.9750, 67.0600),
    "North Nazimabad": (24.9420, 67.0430),
    "PECHS": (24.8700, 67.0600),
    "Saddar": (24.8556, 67.0280),
    "Scheme 33": (24.9500, 67.1500),
    "Shah Faisal Colony": (24.8780, 67.1650),
    "Tariq Road": (24.8740, 67.0640),
}


def area_coords(name: str) -> tuple[float, float]:
    return AREAS[name]
