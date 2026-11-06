"""Benchmark the matching algorithms on synthetic pools (no database needed).

    python -m app.benchmark                        # 5 datasets x pool sizes 70 and 200
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
from .matching.algorithms import ALGORITHMS
from .matching.compat import Rules
from .matching.evaluate import evaluate
from .matching.types import Candidate
from .seed import DEMO, make_students

METRICS = ["match_rate", "circles", "avg_circle_size", "avg_fit", "avg_detour_km", "avg_shared_days",
           "weekly_pkr_saved", "weekly_co2_kg_saved", "runtime_ms"]


def _cand(s: dict, uid: int) -> Candidate:
    return Candidate(uid, area_coords(s["area"]), s["gender"], s["women_only"], tuple(s["methods"]),
                     s.get("has_car", False), s.get("seats", 0), s["schedule"])


def prototype_pool() -> list[Candidate]:
    return [_cand(s | {"has_car": "Classmate drives" in s["methods"] and s["year"] >= 2, "seats": 3}, s["id"])
            for s in DEMO if s["status"] == "approved"]


def rules() -> Rules:
    return Rules(campus=(settings.campus_lat, settings.campus_lng), window_min=settings.schedule_window_min,
                 max_circle_size=settings.max_circle_size)


def _eval(name, pool, r):
    return evaluate(ALGORITHMS[name](pool, r, 0), pool, r, road_factor=settings.road_factor,
                    fuel_price=settings.fuel_price_pkr, km_per_litre=settings.fuel_km_per_litre)


def run(sizes: list[int], datasets: int) -> list[dict]:
    r, rows = rules(), []
    for n in sizes:
        for name in ALGORITHMS:
            res = [_eval(name, [_cand(s, s["user_id"]) for s in make_students(n, 1000 + d)], r) for d in range(datasets)]
            row = {"pool_size": n, "algorithm": name, "datasets": datasets}
            for m in METRICS:
                vals = [x[m] for x in res]
                row[f"{m}_mean"] = round(st.mean(vals), 4)
                row[f"{m}_sd"] = round(st.stdev(vals), 4) if len(vals) > 1 else 0.0
            rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[70, 200])
    ap.add_argument("--datasets", type=int, default=5)
    ap.add_argument("--csv")
    ap.add_argument("--prototype", action="store_true")
    a = ap.parse_args()
    if a.prototype:
        pool = prototype_pool()
        for name in ALGORITHMS:
            print(_eval(name, pool, rules()))
        return
    rows = run(a.sizes, a.datasets)
    print(f"{'n':>4} {'algorithm':<14} {'match rate':>16} {'avg fit':>14} {'detour km':>14} {'Rs saved/wk':>18} {'ms':>8}")
    for x in rows:
        print(f"{x['pool_size']:>4} {x['algorithm']:<14} {x['match_rate_mean']*100:>7.1f}% ± {x['match_rate_sd']*100:>4.1f} "
              f"{x['avg_fit_mean']:>6.1f} ± {x['avg_fit_sd']:>4.1f} {x['avg_detour_km_mean']:>6.2f} ± {x['avg_detour_km_sd']:.2f} "
              f"{x['weekly_pkr_saved_mean']:>9,.0f} ± {x['weekly_pkr_saved_sd']:>6,.0f} {x['runtime_ms_mean']:>8.1f}")
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote {a.csv}")


if __name__ == "__main__":
    main()
