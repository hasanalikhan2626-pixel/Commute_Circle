"""Karachi areas used as privacy-preserving pickup zones (area, never an address).

Coordinates are approximate area centre points (good to ~1 km). The first group is
the prototype's list; the second adds areas near the Korangi Creek campus and other
common neighbourhoods.
"""
from __future__ import annotations

AREAS: dict[str, tuple[float, float]] = {
    # From the prototype
    "Clifton Block 5": (24.818, 67.030),
    "DHA Phase 6": (24.803, 67.060),
    "DHA Phase 8": (24.787, 67.078),
    "Saddar": (24.856, 67.022),
    "PECHS Block 6": (24.866, 67.067),
    "Bahadurabad": (24.880, 67.069),
    "Mehmoodabad": (24.852, 67.090),
    "Gulshan-e-Iqbal Block 13": (24.914, 67.093),
    "Gulshan-e-Iqbal Block 10": (24.926, 67.100),
    "Gulistan-e-Johar Block 15": (24.910, 67.134),
    "Nazimabad No. 3": (24.914, 67.031),
    "North Nazimabad Block H": (24.940, 67.040),
    "Shah Faisal Colony": (24.877, 67.156),
    "Model Colony": (24.896, 67.190),
    "Malir Cantt": (24.940, 67.205),
    "Korangi No. 5": (24.833, 67.138),
    "Defence View": (24.840, 67.080),
    # Added
    "Akhtar Colony": (24.840, 67.078),
    "Bahria Town": (25.010, 67.310),
    "DHA Phase 2": (24.835, 67.050),
    "DHA Phase 5": (24.805, 67.055),
    "DHA Phase 7": (24.815, 67.080),
    "Federal B Area": (24.930, 67.075),
    "Gulberg": (24.933, 67.070),
    "Ibrahim Hyderi": (24.788, 67.145),
    "Kemari": (24.820, 66.980),
    "Korangi Creek": (24.796, 67.135),
    "Landhi": (24.845, 67.205),
    "North Karachi": (24.975, 67.060),
    "Quaidabad": (24.870, 67.230),
    "Scheme 33": (24.950, 67.150),
    "Tariq Road": (24.874, 67.064),
}


def area_coords(name: str) -> tuple[float, float]:
    return AREAS[name]


def short_area(name: str) -> str:
    return name.replace("Gulshan-e-Iqbal", "Gulshan").replace("Gulistan-e-Johar", "Johar")
