"""Benchmark the matching algorithms on synthetic pools (no database needed).

    python -m app.benchmark                       # 5 datasets x pool sizes 60 and 200
    python -m app.benchmark --sizes 100 --datasets 10 --csv results.csv

Reports the mean and standard deviation of each metric across datasets, so
differences between algorithms can be judged against run-to-run variation.
"""
from __future__ import annotations

import argparse
import csv
import statistics as st

from .areas import area_coords
from .config import settings
from .matching.algorithms import ALGORITHMS
from .matching.compat import Rules
from .matching.evaluate import evaluate
from .matching.types import Candidate
from .seed import make_students

METRICS = ["match_rate", "circles", "avg_circle_size", "avg_score", "avg_detour_km", "avg_shared_days",
           "weekly_fuel_pkr_saved", "weekly_co2_kg_saved", "runtime_ms"]


def pool_from_seed(n: int, seed: int) -> list[Candidate]:
    out = []
    for i, s in enumerate(make_students(n, seed), start=1):
        p = s["profile"]
        out.append(Candidate(i, area_coords(p["area"]), p["gender"].value, p["same_gender_only"],
                             p["has_car"], p["seats"], p["schedule"]))
    return out


def run(sizes: list[int], datasets: int) -> list[dict]:
    rules = Rules(campus=(settings.campus_lat, settings.campus_lng), window_min=settings.schedule_window_min,
                  min_shared_days=settings.min_shared_days, max_circle_size=settings.max_circle_size)
    rows = []
    for n in sizes:
        for name, fn in ALGORITHMS.items():
            results = []
            for d in range(datasets):
                pool = pool_from_seed(n, 1000 + d)
                results.append(evaluate(fn(pool, rules, 0), pool, rules, road_factor=settings.road_factor,
                                        km_per_litre=settings.fuel_km_per_litre, fuel_price=settings.fuel_price_pkr))
            row = {"pool_size": n, "algorithm": name, "datasets": datasets}
            for m in METRICS:
                vals = [r[m] for r in results]
                row[f"{m}_mean"] = round(st.mean(vals), 4)
                row[f"{m}_sd"] = round(st.stdev(vals), 4) if len(vals) > 1 else 0.0
            rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[60, 200])
    ap.add_argument("--datasets", type=int, default=5)
    ap.add_argument("--csv")
    a = ap.parse_args()
    rows = run(a.sizes, a.datasets)
    print(f"{'n':>4} {'algorithm':<14} {'match rate':>16} {'compat':>14} {'detour km':>14} {'fuel PKR/wk':>18} {'ms':>8}")
    for r in rows:
        print(f"{r['pool_size']:>4} {r['algorithm']:<14} "
              f"{r['match_rate_mean']*100:>7.1f}% ± {r['match_rate_sd']*100:>4.1f} "
              f"{r['avg_score_mean']:>6.3f} ± {r['avg_score_sd']:.3f} "
              f"{r['avg_detour_km_mean']:>6.2f} ± {r['avg_detour_km_sd']:.2f} "
              f"{r['weekly_fuel_pkr_saved_mean']:>9,.0f} ± {r['weekly_fuel_pkr_saved_sd']:>5,.0f} "
              f"{r['runtime_ms_mean']:>8.1f}")
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote {a.csv}")


if __name__ == "__main__":
    main()
