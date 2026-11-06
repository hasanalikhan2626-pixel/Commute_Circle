"""Fetch road distances and free-flow driving times between every pickup area and campus.

    python -m app.data.fetch_road_matrix          # writes app/data/road_matrix.json

One request to the public OSRM demo server (OpenStreetMap road network). Re-run when areas
or the campus pin change. The output is committed, so the app never calls OSRM at runtime.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import date
from pathlib import Path

from ..areas import AREAS
from ..config import settings

OUT = Path(__file__).with_name("road_matrix.json")
URL = "https://router.project-osrm.org/table/v1/driving/{coords}?annotations=duration,distance"


def main() -> None:
    names = sorted(AREAS) + ["__campus__"]
    pts = [AREAS[n] for n in names[:-1]] + [(settings.campus_lat, settings.campus_lng)]
    coords = ";".join(f"{lng:.6f},{lat:.6f}" for lat, lng in pts)
    req = urllib.request.Request(URL.format(coords=coords), headers={"User-Agent": "CommuteCircle student project"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if data.get("code") != "Ok":
        raise SystemExit(f"OSRM error: {data.get('code')} {data.get('message')}")
    km = [[round(v / 1000, 3) if v is not None else None for v in row] for row in data["distances"]]
    mins = [[round(v / 60, 2) if v is not None else None for v in row] for row in data["durations"]]
    OUT.write_text(json.dumps({
        "source": "OSRM demo server (router.project-osrm.org), OpenStreetMap data, free-flow driving",
        "fetched": date.today().isoformat(),
        "campus": [settings.campus_lat, settings.campus_lng],
        "names": names, "km": km, "minutes": mins,
    }, indent=1))
    print(f"Wrote {OUT} ({len(names)} points)")


if __name__ == "__main__":
    main()
