"""Circle formation.

``build_for`` / ``options_for`` are the prototype's student-facing search ("Find my
circle"): starting from one student, add the classmate who keeps the circle's weakest
pair strongest (60%) and fits the seeker best (40%), up to 4 people.

For the research comparison, three batch algorithms form circles for a whole pool:

A. ``greedy``         Baseline. In sign-up order, each student takes the nearest
                      classmates that keep the circle feasible.
B. ``cluster``        Geography first: k-means on locations, then greedy inside
                      each cluster.
C. ``compatibility``  Proposed method. Runs the student-facing ``build_for`` for the
                      hardest-to-place students first, then a repair pass that puts
                      leftovers into circles with room.

All use the same rules (``compat.feasible``) and are deterministic for a seed.
"""
from __future__ import annotations

import math
import random
import time
from collections.abc import Callable

from .compat import Rules, Scorer, travel_modes
from .geo import haversine_km
from .types import Candidate, MatchResult, ProposedCircle


def _sc(rules: Rules, sc: Scorer | None) -> Scorer:
    return sc if sc is not None else Scorer(rules)


def _candidates(u: Candidate, avail: list[Candidate], sc: Scorer) -> list[Candidate]:
    return [c for c in avail if sc.candidate(u, c)]


def build_for(u: Candidate, avail: list[Candidate], rules: Rules, seed: Candidate | None = None,
              size: int | None = None, sc: Scorer | None = None) -> list[Candidate] | None:
    sc = _sc(rules, sc)
    target = min(size or rules.max_circle_size, rules.max_circle_size)
    cands = _candidates(u, avail, sc)
    grp = [u]
    if seed is not None:
        if seed not in cands or not sc.feasible([u, seed]):
            return None
        grp.append(seed)
    while len(grp) < target:
        best, best_v = None, -1.0
        for c in cands:
            if c in grp or not sc.feasible(grp + [c]):
                continue
            v = min(sc.total(g, c) for g in grp) * 0.6 + sc.total(u, c) * 0.4
            if v > best_v:
                best, best_v = c, v
        if best is None:
            break
        grp.append(best)
    return grp if len(grp) > 1 and sc.feasible(grp) else None


def options_for(u: Candidate, avail: list[Candidate], rules: Rules, n: int = 3) -> list[list[Candidate]]:
    """Up to ``n`` distinct circles for one student, best first (prototype ranking)."""
    sc = Scorer(rules)  # one student's row only: the memoised path is cheaper than a full table
    res: list[list[Candidate]] = []
    base = build_for(u, avail, rules, sc=sc)
    if base:
        res.append(base)
    ranked = sorted(_candidates(u, avail, sc), key=lambda c: -sc.total(u, c))[:6]
    for c in ranked:
        g = build_for(u, avail, rules, seed=c, sc=sc)
        if g and not any({x.user_id for x in r} == {x.user_id for x in g} for r in res):
            res.append(g)
    res.sort(key=lambda g: -(sc.circle_fit(g) + 6 * len(g)))
    return res[:n]


def _finish(name: str, groups: list[list[Candidate]], pool: list[Candidate], sc: Scorer, t0: float) -> MatchResult:
    circles, placed = [], set()
    for g in groups:
        g = sc.arrange(g) if g else None  # founder first
        if g and not placed & {c.user_id for c in g}:
            circles.append(ProposedCircle([c.user_id for c in g], travel_modes(g)[0], sc.circle_fit(g)))
            placed.update(c.user_id for c in g)
    return MatchResult(name, circles, [c.user_id for c in pool if c.user_id not in placed],
                       round((time.perf_counter() - t0) * 1000, 2))


def _repair(groups: list[list[Candidate]], leftovers: list[Candidate], sc: Scorer) -> None:
    for c in leftovers:
        options = [g for g in groups if sc.arrange(g + [c])]
        if options:
            max(options, key=lambda g: min(sc.total(m, c) for m in g)).append(c)


# --- A. Greedy nearest-neighbour baseline -----------------------------------

def greedy(pool: list[Candidate], rules: Rules, seed: int = 0) -> MatchResult:
    t0 = time.perf_counter()
    sc = Scorer(rules, pool)
    placed: set[int] = set()
    groups = []
    for u in sorted(pool, key=lambda c: c.user_id):
        if u.user_id in placed:
            continue
        grp = [u]
        for c in sorted((c for c in pool if c.user_id not in placed and c is not u),
                        key=lambda c: (haversine_km(u.location, c.location), c.user_id)):
            if len(grp) >= rules.max_circle_size:
                break
            if sc.feasible(grp + [c]):
                grp.append(c)
        if len(grp) > 1:
            groups.append(grp)
            placed.update(c.user_id for c in grp)
    return _finish("greedy", groups, pool, sc, t0)


# --- B. Geographic clustering (k-means) --------------------------------------

def _kmeans(points: list[tuple[float, float]], k: int, rng: random.Random, iters: int = 25) -> list[int]:
    """k-means++ on (lat, lng), vectorised with NumPy (haversine distances)."""
    import numpy as np

    P = np.radians(np.array(points))

    def dist(A, C):  # all-pairs haversine (km) between rows of A and rows of C
        dla = C[None, :, 0] - A[:, None, 0]
        dlo = C[None, :, 1] - A[:, None, 1]
        h = np.sin(dla / 2) ** 2 + np.cos(A[:, None, 0]) * np.cos(C[None, :, 0]) * np.sin(dlo / 2) ** 2
        return 2 * 6371.0 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))

    centres = [P[rng.randrange(len(P))]]
    while len(centres) < k:  # k-means++ initialisation
        d2 = dist(P, np.array(centres)).min(axis=1) ** 2
        total = float(d2.sum())
        if total == 0:
            centres.append(P[rng.randrange(len(P))])
            continue
        r, acc = rng.random() * total, 0.0
        for p_, w in zip(P, d2):
            acc += w
            if acc >= r:
                centres.append(p_)
                break
    C = np.array(centres)
    labels = None
    for _ in range(iters):
        new = dist(P, C).argmin(axis=1)
        if labels is not None and (new == labels).all():
            break
        labels = new
        for i in range(k):
            m = labels == i
            if m.any():
                C[i] = P[m].mean(axis=0)
    return [int(v) for v in labels]


def cluster(pool: list[Candidate], rules: Rules, seed: int = 0) -> MatchResult:
    t0 = time.perf_counter()
    sc = Scorer(rules, pool)
    if len(pool) < 2:
        return _finish("cluster", [], pool, sc, t0)
    k = max(1, math.ceil(len(pool) / rules.max_circle_size))
    labels = _kmeans([c.location for c in pool], min(k, len(pool)), random.Random(seed))
    groups, leftovers = [], []
    for lab in sorted(set(labels)):
        free = [c for c, l in zip(pool, labels) if l == lab]
        while free:
            u = free.pop(0)
            grp = [u]
            for c in sorted(free, key=lambda c: -sc.total(u, c)):
                if len(grp) < rules.max_circle_size and sc.feasible(grp + [c]):
                    grp.append(c)
            if len(grp) > 1:
                groups.append(grp)
                free = [c for c in free if c not in grp]
            else:
                leftovers.append(u)
    _repair(groups, leftovers, sc)
    return _finish("cluster", groups, pool, sc, t0)


# --- C. Compatibility-weighted (the prototype's method, proposed) -----------

def compatibility(pool: list[Candidate], rules: Rules, seed: int = 0) -> MatchResult:
    t0 = time.perf_counter()
    sc = Scorer(rules, pool)
    counts = {u.user_id: len(_candidates(u, pool, sc)) for u in pool}
    free = list(pool)
    groups = []
    for u in sorted(pool, key=lambda c: (counts[c.user_id], c.user_id)):  # hardest to place first
        if u not in free:
            continue
        g = build_for(u, free, rules, sc=sc)
        if g:
            groups.append(g)
            free = [c for c in free if c not in g]
    _repair(groups, free, sc)
    return _finish("compatibility", groups, pool, sc, t0)


from .optimise import dbscan_km, genetic, milp  # noqa: E402  (they reuse the helpers above)

ALGORITHMS: dict[str, Callable[[list[Candidate], Rules, int], MatchResult]] = {
    "greedy": greedy,
    "cluster": cluster,
    "compatibility": compatibility,
    "dbscan_km": dbscan_km,
    "genetic": genetic,
}
EXACT = {"milp": milp}  # exact optimum; small pools only (benchmarks, not live matching)
DEFAULT_ALGORITHM = "compatibility"
