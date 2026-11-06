"""RQ2: privacy (pickup-point abstraction) vs route efficiency.

    python -m app.privacy_sim                    # 5 synthetic pools of 200, homes within 1 km of the area centre
    python -m app.privacy_sim --spread 0.5 1.0 1.5 --csv ../docs/privacy-sim.csv

CommuteCircle never collects home addresses, so this is a simulation. Each synthetic
student gets a "true" home scattered uniformly within ``spread`` km of their area's centre.
The same students are then matched three times, with pickups at:

* exact    - the true home (door to door; the least private option),
* landmark - the nearest point of a ``grid`` km landmark grid (proposal 14.5's public
             landmarks, e.g. Maskan Chowrangi), and
* area     - the area centre (what the app does today).

Measured per level (proposal RQ2 targets: route penalty <= 8 %, walk <= 300 m):
* match rate,
* vehicle km per matched student (route through the pickup points), and the penalty
  against the exact level,
* walking distance from the true home to the pickup point,
* k-anonymity: how many students share each pickup point on average (higher = more private).

Distances are straight line x 1.35 for every level (OSRM only covers area centres), so the
comparison is like for like.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import random
import statistics as st

from .areas import area_coords
from .benchmark import rules as base_rules
from .matching import roads
from .matching.algorithms import ALGORITHMS
from .matching.compat import _route_seq
from .matching.geo import haversine_km
from .matching.types import Candidate
from .seed import make_students

KM_PER_DEG_LAT = 111.32


def scatter(centre, spread_km, rng) -> tuple[float, float]:
    """Uniform point in a disc of radius spread_km around centre."""
    r = spread_km * math.sqrt(rng.random())
    a = rng.random() * 2 * math.pi
    dlat = r * math.cos(a) / KM_PER_DEG_LAT
    dlng = r * math.sin(a) / (KM_PER_DEG_LAT * math.cos(math.radians(centre[0])))
    return (centre[0] + dlat, centre[1] + dlng)


def snap(p, grid_km) -> tuple[float, float]:
    """Nearest landmark on a square grid of grid_km spacing."""
    dlat = grid_km / KM_PER_DEG_LAT
    dlng = grid_km / (KM_PER_DEG_LAT * math.cos(math.radians(p[0])))
    return (round(p[0] / dlat) * dlat, round(p[1] / dlng) * dlng)


def _cand(s, loc) -> Candidate:
    return Candidate(s["user_id"], loc, s["gender"], s["women_only"], tuple(s["methods"]), s["has_car"], s["seats"],
                     s["schedule"], s.get("has_bike", False))


def run_level(rows, homes, pickup, rules, algorithm: str) -> dict:
    pool = [_cand(s, pickup[s["user_id"]]) for s in rows]
    res = ALGORITHMS[algorithm](pool, rules, 0)
    by_id = {c.user_id: c for c in pool}
    km_total, matched, walks = 0.0, 0, []
    for circ in res.circles:
        g = [by_id[i] for i in circ.member_ids]
        seq = _route_seq(g, rules.campus)
        pts = [c.location for c in seq] + [rules.campus]
        km_total += sum(haversine_km(pts[i], pts[i + 1]) * rules.road_factor for i in range(len(pts) - 1))
        matched += len(g)
        walks += [haversine_km(homes[c.user_id], c.location) * 1000 for c in g]
    points = {}
    for uid, p in pickup.items():
        points.setdefault((round(p[0], 6), round(p[1], 6)), []).append(uid)
    return {"match_rate": matched / len(pool), "km_per_rider": km_total / matched if matched else 0.0,
            "walk_m_mean": st.mean(walks) if walks else 0.0,
            "walk_within_300m": sum(w <= 300 for w in walks) / len(walks) if walks else 0.0,
            "k_anonymity": st.mean(len(v) for v in points.values())}


def simulate(n=200, datasets=5, spreads=(1.0,), grid_km=0.6, algorithm="compatibility") -> list[dict]:
    os.environ["CC_ROAD_MATRIX"] = "off"  # straight line x 1.35 for every level (like for like)
    roads._table.cache_clear()
    roads._lookup.cache_clear()
    rules = base_rules()
    out = []
    for spread in spreads:
        per = {lvl: [] for lvl in ("exact", "landmark", "area")}
        for d in range(datasets):
            rows = make_students(n, 2000 + d)
            rng = random.Random(9000 + d)
            homes = {s["user_id"]: scatter(area_coords(s["area"]), spread, rng) for s in rows}
            levels = {"exact": homes,
                      "landmark": {u: snap(h, grid_km) for u, h in homes.items()},
                      "area": {s["user_id"]: area_coords(s["area"]) for s in rows}}
            res = {lvl: run_level(rows, homes, pick, rules, algorithm) for lvl, pick in levels.items()}
            for lvl, m in res.items():
                m["route_penalty"] = m["km_per_rider"] / res["exact"]["km_per_rider"] - 1 if res["exact"]["km_per_rider"] else 0.0
                per[lvl].append(m)
        for lvl, ms in per.items():
            row = {"spread_km": spread, "level": lvl, "algorithm": algorithm, "pool_size": n, "datasets": datasets}
            for k in ms[0]:
                vals = [m[k] for m in ms]
                row[f"{k}_mean"] = round(st.mean(vals), 4)
                row[f"{k}_sd"] = round(st.stdev(vals), 4) if len(vals) > 1 else 0.0
            out.append(row)
    os.environ.pop("CC_ROAD_MATRIX", None)
    roads._table.cache_clear()
    roads._lookup.cache_clear()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--datasets", type=int, default=5)
    ap.add_argument("--spread", type=float, nargs="+", default=[1.0])
    ap.add_argument("--grid", type=float, default=0.6)
    ap.add_argument("--algorithm", default="compatibility", choices=list(ALGORITHMS))
    ap.add_argument("--csv")
    a = ap.parse_args()
    rows = simulate(a.n, a.datasets, a.spread, a.grid, a.algorithm)
    print(f"{'spread':>6} {'pickup':<9} {'matched %':>10} {'km/rider':>9} {'penalty %':>10} {'walk m':>8} "
          f"{'<=300 m %':>10} {'k-anon':>7}")
    for r in rows:
        print(f"{r['spread_km']:>6} {r['level']:<9} {r['match_rate_mean'] * 100:>10.1f} {r['km_per_rider_mean']:>9.2f} "
              f"{r['route_penalty_mean'] * 100:>10.1f} {r['walk_m_mean_mean']:>8.0f} {r['walk_within_300m_mean'] * 100:>10.1f} "
              f"{r['k_anonymity_mean']:>7.1f}")
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote {a.csv}")


if __name__ == "__main__":
    main()
