"""Optimisation-based circle formation (proposal sections 14.6-14.7, RQ1).

D. ``dbscan_km``  DBSCAN finds dense neighbourhood pods (1.5 km radius); inside each
                  pod, well-connected students anchor circles and riders are assigned
                  to anchor seats with the Kuhn-Munkres (Hungarian) algorithm; a final
                  pass lets circles form "on the way" across pods.
E. ``genetic``    A grouping Genetic Algorithm over whole partitions, seeded with the
                  heuristic solutions, optimising the multi-objective value below.
F. ``milp``       The exact optimum of the same objective by set partitioning (Mixed-
                  Integer Linear Programming), feasible for small pools; used to
                  measure how close the heuristics get.

All use the same hard rules as the other algorithms (``Scorer.feasible``).

Objective (higher is better), per circle:
    size * (MATCH_WEIGHT + fit) - VEHICLE_WEIGHT - DETOUR_WEIGHT * total rider detour minutes
Matching a student is worth far more than any fit/detour difference, so coverage
comes first; each vehicle used costs VEHICLE_WEIGHT, which favours fuller circles
(RQ1: maximise occupancy); shorter detours break ties. The 12-minute detour limit is a
hard rule (``Scorer.feasible``).
"""
from __future__ import annotations

import math
import random
import time

from .compat import Rules, Scorer
from .types import Candidate, MatchResult

MATCH_WEIGHT = 100.0
VEHICLE_WEIGHT = 60.0
DETOUR_WEIGHT = 2.0


class Valuer:
    """Memoised circle value (the objective above)."""

    def __init__(self, sc: Scorer):
        self.sc = sc
        self._v: dict[frozenset, float | None] = {}

    def value(self, group: list[Candidate]) -> float | None:
        """None if the circle breaks a hard rule."""
        key = frozenset(c.user_id for c in group)
        if key not in self._v:
            group = self.sc.arrange(group)  # value is order-independent; feasibility is per set
            if group is None:
                self._v[key] = None
            else:
                mins = self.sc.rider_detour_min(group).values()
                self._v[key] = (len(group) * (MATCH_WEIGHT + self.sc.circle_fit(group))
                                - VEHICLE_WEIGHT - DETOUR_WEIGHT * sum(mins))
        return self._v[key]

    def total(self, groups: list[list[Candidate]]) -> float:
        return sum(self.value(g) or 0.0 for g in groups)


def objective(groups: list[list[Candidate]], rules: Rules) -> float:
    """Objective value of a set of circles (for comparing algorithms with the MILP optimum)."""
    pool = [c for g in groups for c in g]
    return Valuer(Scorer(rules, pool or None)).total(groups)


# --- D. DBSCAN + Kuhn-Munkres -------------------------------------------------------

def dbscan(points: list[tuple[float, float]], eps_km: float = 1.5, min_samples: int = 3, D=None) -> list[int]:
    """Labels per point (-1 = noise). Haversine distances; vectorised neighbourhood search."""
    import numpy as np

    if D is None:
        P = np.radians(np.array(points))
        dla = P[None, :, 0] - P[:, None, 0]
        dlo = P[None, :, 1] - P[:, None, 1]
        h = np.sin(dla / 2) ** 2 + np.cos(P[:, None, 0]) * np.cos(P[None, :, 0]) * np.sin(dlo / 2) ** 2
        D = 2 * 6371.0 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))
    n = len(points)
    nbrs = [np.flatnonzero(D[i] <= eps_km) for i in range(n)]
    core = [len(nb) >= min_samples for nb in nbrs]
    labels = [-1] * n
    cid = 0
    for i in range(n):
        if labels[i] != -1 or not core[i]:
            continue
        labels[i] = cid
        stack = list(nbrs[i])
        while stack:
            j = int(stack.pop())
            if labels[j] == -1:
                labels[j] = cid
                if core[j]:
                    stack.extend(int(k) for k in nbrs[j] if labels[k] == -1)
        cid += 1
    return labels


def _anchors(free: list[Candidate], sc: Scorer, k: int) -> list[Candidate]:
    """Well-connected students who are not each other's best partners."""
    deg = {c.user_id: sum(sc.ok(c, o) for o in free if o is not c) for c in free}
    order = sorted(free, key=lambda c: (-deg[c.user_id], c.user_id))
    chosen, blocked = [], set()
    for c in order:
        if len(chosen) >= k:
            break
        if c.user_id in blocked or deg[c.user_id] == 0:
            continue
        chosen.append(c)
        best = sorted((o for o in free if o is not c and sc.ok(c, o)), key=lambda o: -sc.total(c, o))
        blocked.update(o.user_id for o in best[: sc.rules.max_circle_size - 1])
    return chosen


def _hungarian_round(free: list[Candidate], sc: Scorer) -> list[list[Candidate]]:
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    size = sc.rules.max_circle_size
    anchors = _anchors(free, sc, math.ceil(len(free) / size))
    if not anchors:
        return []
    riders = [c for c in free if c not in anchors]
    if not riders:
        return []
    slots = [a for a in anchors for _ in range(size - 1)]
    BIG = 1e6
    cost = np.full((len(riders), len(slots)), BIG)
    for i, r in enumerate(riders):
        for j, a in enumerate(slots):
            if sc.ok(r, a):
                cost[i, j] = -(sc.total(a, r) + sc.total(r, a)) / 2
    rows, cols = linear_sum_assignment(cost)
    assigned: dict[int, list[tuple[float, Candidate]]] = {a.user_id: [] for a in anchors}
    for i, j in zip(rows, cols):
        if cost[i, j] < BIG:
            assigned[slots[j].user_id].append((cost[i, j], riders[i]))
    groups = []
    for a in anchors:
        grp = [a]
        for _, r in sorted(assigned[a.user_id], key=lambda t: t[0]):  # best score first
            if sc.feasible(grp + [r]):
                grp.append(r)
        if len(grp) > 1:
            groups.append(grp)
    return groups


def _hungarian(free: list[Candidate], sc: Scorer, rounds: int = 4) -> list[list[Candidate]]:
    groups = []
    for _ in range(rounds):
        new = _hungarian_round(free, sc)
        if not new:
            break
        groups += new
        used = {c.user_id for g in new for c in g}
        free = [c for c in free if c.user_id not in used]
    return groups


def dbscan_km(pool: list[Candidate], rules: Rules, seed: int = 0, eps_km: float = 1.5) -> MatchResult:
    from .algorithms import _finish, _repair

    t0 = time.perf_counter()
    sc = Scorer(rules, pool)
    if len(pool) < 2:
        return _finish("dbscan_km", [], pool, sc, t0)
    labels = dbscan([c.location for c in pool], eps_km, D=sc.D)
    groups: list[list[Candidate]] = []
    pods: dict[int, list[Candidate]] = {}
    for c, lab in zip(pool, labels):
        if lab >= 0:
            pods.setdefault(lab, []).append(c)
    for lab in sorted(pods, key=lambda k: -len(pods[k])):  # densest pods first
        groups += _hungarian(pods[lab], sc)
    used = {c.user_id for g in groups for c in g}
    rest = [c for c in pool if c.user_id not in used]  # noise and leftovers: cross-pod pass
    groups += _hungarian(rest, sc)
    used = {c.user_id for g in groups for c in g}
    _repair(groups, [c for c in pool if c.user_id not in used], sc)
    return _finish("dbscan_km", groups, pool, sc, t0)


# --- E. Genetic Algorithm -------------------------------------------------------------

def _as_groups(result: MatchResult, by_id: dict[int, Candidate]) -> list[list[Candidate]]:
    return [[by_id[i] for i in c.member_ids] for c in result.circles]


def genetic(pool: list[Candidate], rules: Rules, seed: int = 0, pop_size: int = 24, generations: int = 40,
            time_limit_s: float = 5.0) -> MatchResult:
    """Grouping GA. Individuals are sets of feasible circles; genes are whole circles."""
    from .algorithms import _finish, build_for, compatibility, greedy

    t0 = time.perf_counter()
    rng = random.Random(seed)
    sc = Scorer(rules, pool)
    val = Valuer(sc)
    by_id = {c.user_id: c for c in pool}
    if len(pool) < 2:
        return _finish("genetic", [], pool, sc, t0)

    def fitness(ind):
        return val.total(ind)

    def complete(ind):
        """Repair: place unmatched students into circles with room, then form new circles among them."""
        ind = [list(g) for g in ind if val.value(g) is not None]
        used = {c.user_id for g in ind for c in g}
        free = [c for c in pool if c.user_id not in used]
        rng.shuffle(free)
        still = []
        for c in free:
            best, best_gain = None, 0.0
            for g in ind:
                if len(g) < rules.max_circle_size:
                    nv = val.value(g + [c])
                    if nv is not None and nv - val.value(g) > best_gain:
                        best, best_gain = g, nv - val.value(g)
            if best is not None:
                best.append(c)
            else:
                still.append(c)
        while still:
            u = still.pop(0)
            g = build_for(u, still, rules, sc=sc)
            if g:
                ind.append(g)
                still = [c for c in still if c not in g]
        return ind

    def mutate(ind):
        ind = [list(g) for g in ind]
        op = rng.random()
        if op < 0.4 and ind:  # dissolve one circle; repair re-places its members
            ind.pop(rng.randrange(len(ind)))
        elif op < 0.75 and len(ind) >= 2:  # swap two members between circles
            a, b = rng.sample(range(len(ind)), 2)
            i, j = rng.randrange(len(ind[a])), rng.randrange(len(ind[b]))
            ga, gb = ind[a][:], ind[b][:]
            ga[i], gb[j] = ind[b][j], ind[a][i]
            if val.value(ga) is not None and val.value(gb) is not None:
                ind[a], ind[b] = ga, gb
        elif ind:  # move one member to another circle with room
            a = rng.randrange(len(ind))
            if len(ind[a]) > 2:
                m = ind[a].pop(rng.randrange(len(ind[a])))
                targets = [g for g in ind if g is not ind[a] and len(g) < rules.max_circle_size
                           and val.value(g + [m]) is not None]
                (rng.choice(targets) if targets else ind[a]).append(m)
        return complete(ind)

    def crossover(p1, p2):
        """Keep about half of p1's circles, add p2's circles that don't clash, then repair."""
        child = [g for g in p1 if rng.random() < 0.5]
        used = {c.user_id for g in child for c in g}
        for g in sorted(p2, key=lambda g: -(val.value(g) or 0)):
            ids = {c.user_id for c in g}
            if not ids & used:
                child.append(g)
                used |= ids
        return complete(child)

    seeds = [_as_groups(f(pool, rules, seed), by_id) for f in (compatibility, greedy, dbscan_km)]
    population = [complete(s) for s in seeds]
    while len(population) < pop_size:
        population.append(mutate(rng.choice(seeds)))
    for _ in range(generations):
        if time.perf_counter() - t0 > time_limit_s:
            break
        population.sort(key=fitness, reverse=True)
        nxt = population[:2]  # elitism
        while len(nxt) < pop_size:
            p1 = max(rng.sample(population, 3), key=fitness)  # tournament selection
            p2 = max(rng.sample(population, 3), key=fitness)
            child = crossover(p1, p2) if rng.random() < 0.7 else [list(g) for g in p1]
            if rng.random() < 0.6:
                child = mutate(child)
            nxt.append(child)
        population = nxt
    best = max(population, key=fitness)
    return _finish("genetic", best, pool, sc, t0)


# --- F. Exact optimum (MILP set partitioning) -----------------------------------------

def feasible_circles(pool: list[Candidate], sc: Scorer, limit: int = 300_000) -> list[list[Candidate]]:
    """Every feasible circle of 2..max size (cliques of the compatibility graph)."""
    n = len(pool)
    adj = [{j for j in range(n) if j != i and sc.ok(pool[i], pool[j])} for i in range(n)]
    out: list[list[Candidate]] = []

    def grow(members: list[int], cand: set[int]):
        if len(members) >= 2:
            g = sc.arrange([pool[i] for i in members])  # any member may be the founder
            if g is not None:
                out.append(g)
                if len(out) > limit:
                    raise OverflowError
        if len(members) < sc.rules.max_circle_size:
            for j in sorted(cand):
                if j > members[-1]:
                    grow(members + [j], cand & adj[j])

    for i in range(n):
        grow([i], adj[i])
    return out


def milp(pool: list[Candidate], rules: Rules, seed: int = 0, max_pool: int = 90,
         time_limit_s: float = 60.0) -> MatchResult:
    """Exact optimum of the objective. Raises ValueError for pools too large to enumerate."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp as solve
    from scipy.sparse import lil_matrix

    from .algorithms import _finish

    t0 = time.perf_counter()
    sc = Scorer(rules, pool)
    if len(pool) > max_pool:
        raise ValueError(f"MILP is limited to {max_pool} students (got {len(pool)})")
    try:
        cols = feasible_circles(pool, sc)
    except OverflowError as e:
        raise ValueError("Too many feasible circles to solve exactly") from e
    val = Valuer(sc)
    cols = [g for g in cols if val.value(g) is not None]
    if not cols:
        return _finish("milp", [], pool, sc, t0)
    idx = {c.user_id: i for i, c in enumerate(pool)}
    A = lil_matrix((len(pool), len(cols)))
    for j, g in enumerate(cols):
        for c in g:
            A[idx[c.user_id], j] = 1
    c_vec = -np.array([val.value(g) for g in cols])  # milp minimises
    res = solve(c_vec, constraints=LinearConstraint(A.tocsr(), 0, 1), integrality=np.ones(len(cols)),
                bounds=Bounds(0, 1), options={"time_limit": time_limit_s})
    if res.x is None:
        raise ValueError(f"MILP solver failed: {res.message}")
    chosen = [cols[j] for j in np.flatnonzero(res.x > 0.5)]
    out = _finish("milp", chosen, pool, sc, t0)
    out.optimal = bool(res.status == 0)
    return out
