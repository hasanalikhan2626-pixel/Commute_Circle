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

from .compat import Rules, circle_fit, feasible, pair_fit, travel_modes
from .geo import haversine_km
from .types import Candidate, MatchResult, ProposedCircle


def _candidates(u: Candidate, avail: list[Candidate], rules: Rules) -> list[Candidate]:
    out = []
    for c in avail:
        if c.user_id == u.user_id or frozenset((u.user_id, c.user_id)) in rules.excluded:
            continue
        p = pair_fit(u, c, rules.campus)
        if p and p.total >= rules.min_fit and p.good_days:
            out.append(c)
    return out


def build_for(u: Candidate, avail: list[Candidate], rules: Rules, seed: Candidate | None = None,
              size: int | None = None) -> list[Candidate] | None:
    target = min(size or rules.max_circle_size, rules.max_circle_size)
    cands = _candidates(u, avail, rules)
    grp = [u]
    if seed is not None:
        if seed not in cands or not feasible([u, seed], rules):
            return None
        grp.append(seed)
    while len(grp) < target:
        best, best_v = None, -1.0
        for c in cands:
            if c in grp or not feasible(grp + [c], rules):
                continue
            ps = [pair_fit(g, c, rules.campus) for g in grp]
            v = min(p.total for p in ps) * 0.6 + pair_fit(u, c, rules.campus).total * 0.4
            if v > best_v:
                best, best_v = c, v
        if best is None:
            break
        grp.append(best)
    return grp if len(grp) > 1 and feasible(grp, rules) else None


def options_for(u: Candidate, avail: list[Candidate], rules: Rules, n: int = 3) -> list[list[Candidate]]:
    """Up to ``n`` distinct circles for one student, best first (prototype ranking)."""
    res: list[list[Candidate]] = []
    base = build_for(u, avail, rules)
    if base:
        res.append(base)
    ranked = sorted(_candidates(u, avail, rules), key=lambda c: -pair_fit(u, c, rules.campus).total)[:6]
    for c in ranked:
        g = build_for(u, avail, rules, seed=c)
        if g and not any({x.user_id for x in r} == {x.user_id for x in g} for r in res):
            res.append(g)
    res.sort(key=lambda g: -(circle_fit(g, rules.campus) + 6 * len(g)))
    return res[:n]


def _finish(name: str, groups: list[list[Candidate]], pool: list[Candidate], rules: Rules, t0: float) -> MatchResult:
    circles, placed = [], set()
    for g in groups:
        if feasible(g, rules):
            circles.append(ProposedCircle([c.user_id for c in g], travel_modes(g)[0], circle_fit(g, rules.campus)))
            placed.update(c.user_id for c in g)
    return MatchResult(name, circles, [c.user_id for c in pool if c.user_id not in placed],
                       round((time.perf_counter() - t0) * 1000, 2))


def _repair(groups: list[list[Candidate]], leftovers: list[Candidate], rules: Rules) -> None:
    for c in leftovers:
        options = [g for g in groups if feasible(g + [c], rules)]
        if options:
            max(options, key=lambda g: min(pair_fit(m, c, rules.campus).total for m in g)).append(c)


# --- A. Greedy nearest-neighbour baseline -----------------------------------

def greedy(pool: list[Candidate], rules: Rules, seed: int = 0) -> MatchResult:
    t0 = time.perf_counter()
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
            if feasible(grp + [c], rules):
                grp.append(c)
        if len(grp) > 1:
            groups.append(grp)
            placed.update(c.user_id for c in grp)
    return _finish("greedy", groups, pool, rules, t0)


# --- B. Geographic clustering (k-means) --------------------------------------

def _kmeans(points: list[tuple[float, float]], k: int, rng: random.Random, iters: int = 25) -> list[int]:
    centres = [points[rng.randrange(len(points))]]
    while len(centres) < k:  # k-means++ initialisation
        d2 = [min(haversine_km(p, c) ** 2 for c in centres) for p in points]
        total = sum(d2)
        if total == 0:
            centres.append(points[rng.randrange(len(points))])
            continue
        r, acc = rng.random() * total, 0.0
        for p, w in zip(points, d2):
            acc += w
            if acc >= r:
                centres.append(p)
                break
    labels: list[int] = []
    for _ in range(iters):
        new = [min(range(k), key=lambda i: haversine_km(p, centres[i])) for p in points]
        if new == labels:
            break
        labels = new
        for i in range(k):
            ms = [p for p, lab in zip(points, labels) if lab == i]
            if ms:
                centres[i] = (sum(p[0] for p in ms) / len(ms), sum(p[1] for p in ms) / len(ms))
    return labels


def cluster(pool: list[Candidate], rules: Rules, seed: int = 0) -> MatchResult:
    t0 = time.perf_counter()
    if len(pool) < 2:
        return _finish("cluster", [], pool, rules, t0)
    k = max(1, math.ceil(len(pool) / rules.max_circle_size))
    labels = _kmeans([c.location for c in pool], min(k, len(pool)), random.Random(seed))
    groups, leftovers = [], []
    for lab in sorted(set(labels)):
        free = [c for c, l in zip(pool, labels) if l == lab]
        while free:
            u = free.pop(0)
            grp = [u]
            for c in sorted(free, key=lambda c: -pair_fit(u, c, rules.campus).total if pair_fit(u, c, rules.campus) else 0):
                if len(grp) < rules.max_circle_size and feasible(grp + [c], rules):
                    grp.append(c)
            if len(grp) > 1:
                groups.append(grp)
                free = [c for c in free if c not in grp]
            else:
                leftovers.append(u)
    _repair(groups, leftovers, rules)
    return _finish("cluster", groups, pool, rules, t0)


# --- C. Compatibility-weighted (the prototype's method, proposed) -----------

def compatibility(pool: list[Candidate], rules: Rules, seed: int = 0) -> MatchResult:
    t0 = time.perf_counter()
    counts = {u.user_id: len(_candidates(u, pool, rules)) for u in pool}
    free = list(pool)
    groups = []
    for u in sorted(pool, key=lambda c: (counts[c.user_id], c.user_id)):  # hardest to place first
        if u not in free:
            continue
        g = build_for(u, free, rules)
        if g:
            groups.append(g)
            free = [c for c in free if c not in g]
    _repair(groups, free, rules)
    return _finish("compatibility", groups, pool, rules, t0)


ALGORITHMS: dict[str, Callable[[list[Candidate], Rules, int], MatchResult]] = {
    "greedy": greedy,
    "cluster": cluster,
    "compatibility": compatibility,
}
DEFAULT_ALGORITHM = "compatibility"
