"""Benchmark the matching algorithms on synthetic pools (no database needed).

    python -m app.benchmark                        # 5 datasets x pool sizes 70, 200, 500
    python -m app.benchmark --sizes 100 --datasets 10 --csv results.csv
    python -m app.benchmark --prototype            # the prototype's 71 students

Reports mean and standard deviation across datasets, so differences between
algorithms can be judged against run-to-run variation.
"""
from __future__ import annotations

import argparse
import csv
import statistics as st

from .areas import area_coords
from .config import settings
import random
import time

from .matching.algorithms import ALGORITHMS, EXACT, options_for
from .matching.compat import Rules
from .matching.evaluate import evaluate
from .matching.types import Candidate
from .seed import DEMO, make_students

METRICS = ["match_rate", "circles", "avg_circle_size", "occupancy", "avg_fit", "avg_rider_detour_min",
           "max_rider_detour_min", "riders_within_limit", "avg_shared_days", "weekly_pkr_saved", "weekly_co2_kg_saved",
           "objective", "gap_to_optimum", "runtime_ms"]
EXACT_MAX = 90  # the MILP optimum is computed for pools up to this size


def _cand(s: dict, uid: int) -> Candidate:
    return Candidate(uid, area_coords(s["area"]), s["gender"], s["women_only"], tuple(s["methods"]),
                     s.get("has_car", False), s.get("seats", 0), s["schedule"], s.get("has_bike", False))


def prototype_pool() -> list[Candidate]:
    return [_cand(s | {"has_car": "Classmate drives" in s["methods"] and s["year"] >= 2, "seats": 3}, s["id"])
            for s in DEMO if s["status"] == "approved"]


def rules() -> Rules:
    return Rules(campus=(settings.campus_lat, settings.campus_lng), window_min=settings.schedule_window_min,
                 max_circle_size=settings.max_circle_size, max_detour_min=settings.max_detour_min,
                 speed_kmh=settings.avg_speed_kmh, road_factor=settings.road_factor)


def _eval(name, pool, r):
    fn = ALGORITHMS.get(name) or EXACT[name]
    return evaluate(fn(pool, r, 0), pool, r, road_factor=settings.road_factor,
                    fuel_price=settings.fuel_price_pkr, km_per_litre=settings.fuel_km_per_litre, speed_kmh=settings.avg_speed_kmh)


def student_latency(pool, r, n=30, seed=0) -> list[float]:
    """Seconds for one student's 'Find my circle' search (the proposal's <= 1.5 s turn)."""
    rng = random.Random(seed)
    out = []
    for u in rng.sample(pool, min(n, len(pool))):
        t = time.perf_counter()
        options_for(u, pool, r)
        out.append(time.perf_counter() - t)
    return out


def run(sizes: list[int], datasets: int) -> tuple[list[dict], list[dict]]:
    r, rows, lat = rules(), [], []
    names = list(ALGORITHMS) + list(EXACT)
    for n in sizes:
        per = {name: [] for name in names}
        lat_n = []
        for d in range(datasets):
            pool = [_cand(s, s["user_id"]) for s in make_students(n, 1000 + d)]
            res = {name: _eval(name, pool, r) for name in ALGORITHMS}
            if n <= EXACT_MAX:
                res["milp"] = _eval("milp", pool, r)
            opt = res.get("milp", {}).get("objective")
            for name, m in res.items():
                m["gap_to_optimum"] = round(1 - m["objective"] / opt, 4) if opt else None
                per[name].append(m)
            lat_n += student_latency(pool, r, seed=d)
        for name, results in per.items():
            if not results:
                continue
            row = {"pool_size": n, "algorithm": name, "datasets": datasets}
            for m in METRICS:
                vals = [x[m] for x in results if x.get(m) is not None]
                row[f"{m}_mean"] = round(st.mean(vals), 4) if vals else None
                row[f"{m}_sd"] = round(st.stdev(vals), 4) if len(vals) > 1 else 0.0
            rows.append(row)
        lat_n.sort()
        lat.append({"pool_size": n, "searches": len(lat_n), "mean_s": round(st.mean(lat_n), 4),
                    "p95_s": round(lat_n[int(0.95 * (len(lat_n) - 1))], 4), "max_s": round(lat_n[-1], 4)})
    return rows, lat


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[70, 200, 500])
    ap.add_argument("--datasets", type=int, default=5)
    ap.add_argument("--csv")
    ap.add_argument("--prototype", action="store_true")
    a = ap.parse_args()
    if a.prototype:
        pool = prototype_pool()
        for name in list(ALGORITHMS) + (["milp"] if len(pool) <= EXACT_MAX else []):
            print(_eval(name, pool, rules()))
        return
    rows, lat = run(a.sizes, a.datasets)
    pm = lambda x, k, f=1, d=1: "-" if x[f"{k}_mean"] is None else f"{x[f'{k}_mean'] * f:.{d}f}±{x[f'{k}_sd'] * f:.{d}f}"  # noqa: E731
    print(f"{'n':>4} {'algorithm':<14} {'matched %':>11} {'fit':>10} {'detour min':>10} {'max':>6} {'<=12min %':>11} "
          f"{'occupancy':>10} {'gap to opt %':>12} {'s':>6}")
    for x in rows:
        print(f"{x['pool_size']:>4} {x['algorithm']:<14} {pm(x, 'match_rate', 100):>11} {pm(x, 'avg_fit'):>10} "
              f"{pm(x, 'avg_rider_detour_min'):>10} {x['max_rider_detour_min_mean']:>6.1f} {pm(x, 'riders_within_limit', 100):>11} "
              f"{pm(x, 'occupancy', 1, 2):>10} {pm(x, 'gap_to_optimum', 100):>12} {x['runtime_ms_mean'] / 1000:>6.2f}")
    print("\nOne student's Find my circle search (target <= 1.5 s):")
    for x in lat:
        print(f"  {x['pool_size']:>4} students: mean {x['mean_s']:.3f} s, 95th percentile {x['p95_s']:.3f} s, max {x['max_s']:.3f} s"
              f" ({x['searches']} searches)")
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote {a.csv}")


if __name__ == "__main__":
    main()
