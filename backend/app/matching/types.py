from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Candidate:
    """What the matcher needs about a student, decoupled from the ORM so the
    algorithms are pure functions that can be tested and benchmarked alone."""

    user_id: int
    location: tuple[float, float]
    gender: str  # "female" | "male"
    women_only: bool
    methods: tuple[str, ...]
    has_car: bool
    seats: int
    schedule: dict  # "Mon" -> {"in": "HH:MM", "out": "HH:MM"}; missing day = not on campus
    has_bike: bool = False  # can offer "Motorbike pillion"


@dataclass
class ProposedCircle:
    member_ids: list[int]
    mode: str
    fit: int = 0


@dataclass
class MatchResult:
    algorithm: str
    circles: list[ProposedCircle] = field(default_factory=list)
    unmatched: list[int] = field(default_factory=list)
    runtime_ms: float = 0.0
