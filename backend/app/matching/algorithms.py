"""Three circle-formation algorithms compared in the research component.

A. ``greedy``         Baseline. Each driver takes the nearest riders that fit.
B. ``cluster``        Geography first: k-means on locations, then split each
                      cluster into feasible circles.
C. ``compatibility``  Proposed method. Seeds circles from the hardest-to-place
                      drivers and grows them by highest average pairwise
                      compatibility, followed by a repair pass that places
                      leftovers into circles with spare seats.

All three are pure functions of (candidates, rules) and are deterministic for a
given seed, so results are reproducible for the evaluation chapter.
"""
from __future__ import annotations

import math
import random
import time
from collections.abc import Callable

from .compat import Rules, can_grow, circle_score, feasible, pair_compatible, pair_score
from .geo import haversine_km
from .types import Candidate, MatchResult, ProposedCircle


def _finish(name: str, groups: list[list[Candidate]], pool: list[Candidate], rules: Rules, t0: float) -> MatchResult:
    circles, placed = [], set()
    for g in groups:
        if feasible(g, rules):
            circles.append(ProposedCircle(
                member_ids=[c.user_id for c in g],
                driver_ids=[c.user_id for c in g if c.has_car],
                score=round(circle_score(g, rules), 4),
            ))
            placed.update(c.user_id for c in g)
    unmatched = [c.user_id for c in pool if c.user_id not in placed]
    return MatchResult(name, circles, unmatched, round((time.perf_counter() - t0) * 1000, 2))


def _absorb_leftovers(groups: list[list[Candidate]], leftovers: list[Candidate], rules: Rules,
                      by_score: bool) -> list[Candidate]:
    """Put each leftover into the best existing group that stays feasible."""
    still = []
    for c in leftovers:
        options = [g for g in groups if feasible(g + [c], rules)]
        if not options:
            still.append(c)
            continue
        if by_score:
            best = max(options, key=lambda g: sum(pair_score(c, m, rules) for m in g) / len(g))
        else:
            best = min(options, key=lambda g: min(haversine_km(c.location, m.location) for m in g))
        best.append(c)
    return still


# --- A. Greedy nearest-neighbour baseline -----------------------------------

def greedy(pool: list[Candidate], rules: Rules, seed: int = 0) -> MatchResult:
    t0 = time.perf_counter()
    drivers = sorted((c for c in pool if c.has_car and c.seats > 0), key=lambda c: (-c.seats, c.user_id))
    free = {c.user_id: c for c in pool if not (c.has_car and c.seats > 0)}
    groups = []
    for d in drivers:
        group = [d]
        for r in sorted(free.values(), key=lambda r: (haversine_km(d.location, r.location), r.user_id)):
            if len(group) >= min(rules.max_circle_size, d.seats + 1):
                break
            if feasible(group + [r], rules):
                group.append(r)
                del free[r.user_id]
        groups.append(group)
    lonely = [g[0] for g in groups if len(g) == 1]
    groups = [g for g in groups if len(g) > 1]
    _absorb_leftovers(groups, lonely, rules, by_score=False)
    return _finish("greedy", groups, pool, rules, t0)


# --- B. Geographic clustering (k-means) --------------------------------------

def _kmeans(points: list[tuple[float, float]], k: int, rng: random.Random, iters: int = 25) -> list[int]:
    # k-means++ initialisation
    centres = [points[rng.randrange(len(points))]]
    while len(centres) < k:
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
    labels = [0] * len(points)
    for _ in range(iters):
        new = [min(range(k), key=lambda i: haversine_km(p, centres[i])) for p in points]
        if new == labels and _ > 0:
            break
        labels = new
        for i in range(k):
            members = [p for p, lab in zip(points, labels) if lab == i]
            if members:
                centres[i] = (sum(p[0] for p in members) / len(members), sum(p[1] for p in members) / len(members))
    return labels


def cluster(pool: list[Candidate], rules: Rules, seed: int = 0) -> MatchResult:
    t0 = time.perf_counter()
    if len(pool) < 2:
        return _finish("cluster", [], pool, rules, t0)
    rng = random.Random(seed)
    k = max(1, math.ceil(len(pool) / (rules.max_circle_size - 1)))
    labels = _kmeans([c.location for c in pool], min(k, len(pool)), rng)
    groups, leftovers = [], []
    for lab in sorted(set(labels)):
        members = [c for c, l in zip(pool, labels) if l == lab]
        drivers = sorted((c for c in members if c.has_car and c.seats > 0), key=lambda c: -c.seats)
        free = [c for c in members if c not in drivers]
        for d in drivers:
            group = [d]
            for r in list(free):
                if feasible(group + [r], rules):
                    group.append(r)
                    free.remove(r)
            (groups if len(group) > 1 else leftovers).append(group if len(group) > 1 else d)
        leftovers.extend(free)
    _absorb_leftovers(groups, leftovers, rules, by_score=False)
    return _finish("cluster", groups, pool, rules, t0)


# --- C. Compatibility-weighted greedy with repair (proposed) ----------------

def compatibility(pool: list[Candidate], rules: Rules, seed: int = 0) -> MatchResult:
    t0 = time.perf_counter()
    by_id = {c.user_id: c for c in pool}
    neighbours: dict[int, set[int]] = {c.user_id: set() for c in pool}
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            if pair_compatible(a, b, rules):
                neighbours[a.user_id].add(b.user_id)
                neighbours[b.user_id].add(a.user_id)

    unplaced = set(by_id)
    drivers = [c for c in pool if c.has_car and c.seats > 0]
    # Most constrained first: drivers with the fewest compatible partners.
    drivers.sort(key=lambda d: (len(neighbours[d.user_id]), d.user_id))
    groups: list[list[Candidate]] = []
    for d in drivers:
        if d.user_id not in unplaced:
            continue
        group = [d]
        while True:
            ids = {m.user_id for m in group}
            cands = set.intersection(*(neighbours[i] for i in ids)) & unplaced - ids
            # Prefer riders over spare drivers so cars are not wasted.
            ranked = sorted(
                (by_id[i] for i in cands),
                key=lambda c: (c.has_car, -sum(pair_score(c, m, rules) for m in group) / len(group), c.user_id),
            )
            added = False
            for c in ranked:
                if can_grow(group + [c], rules):
                    group.append(c)
                    added = True
                    break
            if not added:
                break
        if len(group) > 1:
            groups.append(group)
            unplaced -= {m.user_id for m in group}

    # Repair: place leftovers (including unused drivers) into circles with room.
    still = _absorb_leftovers(groups, [by_id[i] for i in sorted(unplaced)], rules, by_score=True)
    # Second chance: leftover riders + leftover drivers may form new circles.
    if still:
        sub = compatibility_core_pass(still, rules)
        groups.extend(sub)
    return _finish("compatibility", groups, pool, rules, t0)


def compatibility_core_pass(pool: list[Candidate], rules: Rules) -> list[list[Candidate]]:
    groups, remaining = [], list(pool)
    for d in [c for c in pool if c.has_car and c.seats > 0]:
        if d not in remaining:
            continue
        group = [d]
        for c in sorted(remaining, key=lambda c: -pair_score(d, c, rules)):
            if c is not d and c not in group and can_grow(group + [c], rules):
                group.append(c)
        if len(group) > 1:
            groups.append(group)
            for m in group:
                remaining.remove(m)
    return groups


ALGORITHMS: dict[str, Callable[[list[Candidate], Rules, int], MatchResult]] = {
    "greedy": greedy,
    "cluster": cluster,
    "compatibility": compatibility,
}
DEFAULT_ALGORITHM = "compatibility"
